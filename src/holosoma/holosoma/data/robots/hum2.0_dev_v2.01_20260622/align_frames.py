#!/usr/bin/env python3
"""
Align all MuJoCo body frames with the world frame (z-up, x-forward) while
preserving world poses of bodies, geoms, sites, cameras, joints, and inertials.

This version uses MuJoCo's built-in math primitives:
  - mju_rotVecQuat : rotate vector by quaternion
  - mju_mulQuat    : quaternion multiply
  - mju_normalize4 : normalize quaternion

It also resolves joint defaults (global/class + childclass) so inherited axes
are rotated and then written explicitly on the <joint>.
"""

import sys
import xml.etree.ElementTree as ET

import mujoco as mj  # MuJoCo native Python bindings
import numpy as np

IDENT = np.array([1.0, 0.0, 0.0, 0.0], dtype=float)


# ---------- tiny wrappers over MuJoCo math ----------
def qmul(q2, q1):
    """Return q2 ⊗ q1 (w,x,y,z)."""
    res = np.empty(4, dtype=float)
    mj.mju_mulQuat(res, np.asarray(q2, float), np.asarray(q1, float))
    return res


def qnormalize(q):
    q = np.asarray(q, float).copy()
    mj.mju_normalize4(q)
    return q


def rot_vec_quat(v, q):
    """Rotate 3-vector v by quaternion q."""
    out = np.empty(3, dtype=float)
    mj.mju_rotVecQuat(out, np.asarray(v, float), np.asarray(q, float))
    return out


# ---------- XML utils ----------
def get_vec(elem, key, default):
    s = elem.get(key)
    return list(default) if s is None else [float(x) for x in s.split()]


def set_vec(elem, key, vec):
    elem.set(key, " ".join(f"{float(x):.8g}" for x in vec))


def get_quat(elem, key="quat"):
    if elem.get(key) is None:
        return IDENT.copy()
    return np.array([float(x) for x in elem.get(key).split()], dtype=float)


def set_quat(elem, q, key="quat"):
    q = qnormalize(q)
    elem.set(key, " ".join(f"{x:.8g}" for x in q))


# ---------- parse <default> joint attributes (global + classes, with nesting) ----------
def _merge(dst, src):
    if src:
        dst.update(src)
    return dst


def parse_joint_defaults(root):
    """
    Returns dict: class_name_or_None -> {attr_name: attr_value}
    where None is the global default.
    """
    maps = {}

    def collect_joint_attrs(elem):
        merged = {}
        for j in elem.findall("joint"):
            _merge(merged, j.attrib)
        return merged

    def dfs(def_elem, inherited):
        local = dict(inherited)
        _merge(local, collect_joint_attrs(def_elem))
        key = def_elem.get("class") or None
        maps[key] = {**maps.get(key, {}), **local}
        for child in def_elem.findall("default"):
            dfs(child, local)

    for d in root.findall("default"):
        dfs(d, {})
    return maps


def resolve_joint_attr(joint_elem, active_childclass, joint_defaults, key):
    # element attribute
    if joint_elem.get(key) is not None:
        return joint_elem.get(key)
    # class / childclass
    jcls = joint_elem.get("class") or active_childclass
    if jcls in joint_defaults and key in joint_defaults[jcls]:
        return joint_defaults[jcls][key]
    # global
    if None in joint_defaults and key in joint_defaults[None]:
        return joint_defaults[None][key]
    return None


# ---------- main transform ----------
def rotate_and_write_joint_axis(joint_elem, q_body, active_childclass, joint_defaults):
    # Skip ball joints (no single axis)
    jtype = resolve_joint_attr(joint_elem, active_childclass, joint_defaults, "type")
    if jtype and jtype.strip().lower() == "ball":
        return

    axis_str = resolve_joint_attr(joint_elem, active_childclass, joint_defaults, "axis")
    if axis_str is None:
        return
    a = np.array([float(x) for x in axis_str.split()], dtype=float)
    aR = rot_vec_quat(a, q_body)
    set_vec(joint_elem, "axis", aR)  # write explicitly to override class/default


def align_body_frames(body_elem, joint_defaults, inherited_childclass=None):
    # Track active childclass (applies to contained elements missing 'class')
    active_childclass = body_elem.get("childclass") or inherited_childclass

    # THIS body's local rotation relative to parent
    q_body = get_quat(body_elem, "quat")

    # 1) zero out this body's local rotation
    set_quat(body_elem, IDENT, "quat")

    # 2) push rotation into children to preserve world pose
    for child in list(body_elem):
        tag = child.tag

        if tag in {"geom", "site", "camera", "light"}:
            # rotate local pos
            pos = get_vec(child, "pos", (0.0, 0.0, 0.0))
            set_vec(child, "pos", rot_vec_quat(pos, q_body))
            # rotate local quat
            q_local = get_quat(child, "quat")
            set_quat(child, qmul(q_body, q_local), "quat")

        elif tag == "joint":
            rotate_and_write_joint_axis(child, q_body, active_childclass, joint_defaults)

        elif tag == "freejoint":
            pass  # no axis

        elif tag == "body":
            # rotate child pose, then recurse
            pos = get_vec(child, "pos", (0.0, 0.0, 0.0))
            set_vec(child, "pos", rot_vec_quat(pos, q_body))
            q_child = get_quat(child, "quat")
            set_quat(child, qmul(q_body, q_child))
            align_body_frames(child, joint_defaults, inherited_childclass=active_childclass)

        elif tag == "inertial":
            # rotate inertial orientation if present
            if child.get("quat") is not None:
                set_quat(child, qmul(q_body, get_quat(child, "quat")))
            # rotate inertial position
            set_vec(child, "pos", rot_vec_quat(get_vec(child, "pos", (0, 0, 0)), q_body))
        # else: ignore


def process(xml_in, xml_out):
    tree = ET.parse(xml_in)
    root = tree.getroot()

    joint_defaults = parse_joint_defaults(root)

    worldbody = root.find("worldbody")
    if worldbody is None:
        raise RuntimeError("No <worldbody> found.")

    for body in worldbody.findall("body"):
        align_body_frames(body, joint_defaults, inherited_childclass=None)

    tree.write(xml_out, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python align_frames.py input.xml output.xml")
        sys.exit(1)
    process(sys.argv[1], sys.argv[2])
    print(f"Wrote aligned MJCF to: {sys.argv[2]}")
