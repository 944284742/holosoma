# xhumanoid_v201 — RL integration handoff

This model (`assets/hum2.0_dev_v2.01_20260622/`) is exported and converted, but **not yet
wired into the RL pipeline**. This doc is the recipe to do that, so you don't have to
reverse-engineer it. All paths/symbols below were verified against the repo on 2026-06-24.

## What's already done (PR #202)

| File | What |
|---|---|
| `config.json` | Onshape export config (model url, `outputFormat: mujoco`, real masses) |
| `robot.xml` | raw onshape-to-robot MJCF export (63.68 kg, 32/32 links real mass) |
| `output.xml` | **canonical MJCF**, produced by `robot_xml_cli.py` from `robot.xml` |
| `urdf/xhumanoid_v201.urdf` | URDF, produced by `convert_urdf.py` from `output.xml` |
| `assets/merged/*_visual.stl` | visual meshes for the MJCF (committed) |
| `urdf/converted_*.stl` | visual meshes for the URDF (committed) |

Everything in `output.xml` is reproducible from `get_default_config()` in
`assets/robot_xml_transformer/config/transformation_config.py` + one CLI run — no hand-edits:
+90° yaw (X-forward, Z-up) & auto spawn height, 18 chirality flips (G1 convention),
joint+actuator order (L leg · R leg · waist · L arm · R arm · head), feet = 2×3 plane-fit
coin cylinders, and t=0 self-collision excludes.

> ⚠️ **Motors are placeholders.** The `EC_*` actuator/default classes carry **ENCOS**
> torque/armature values, not the real **MAXON** specs. This is the same placeholder set the
> RL side already uses (`actuator_constants.py`, whose top comment says *"all of this has to be
> updated to be more similar to the real robot"*). Your **Maxon multimodel work (PR #191)** is
> the real-motor source — see step 4.

## How the RL pipeline consumes a robot (verified)

- RL loads **URDF** via IsaacLab `UrdfFileCfg` — e.g. `source/walking/walking/robots/xhum15.py`
  (`XHUM15_CYLINDER_CFG`, `asset_path=f"{ASSET_DIR}/xhum/urdf/v15/humanoid.urdf"`).
  IsaacLab converts URDF→USD **at load time and caches it** — there is no manual USD step, and
  no `.usd` is committed.
- `ASSET_DIR = source/walking/walking/assets` (`walking/assets/__init__.py`). RL assets live
  under it, e.g. `xhum/urdf/v15/humanoid.urdf` + `xhum/meshes/xhum15/converted_*.stl`.
- A **robot cfg** (`robots/<name>.py`) defines the `ArticulationCfg` (spawn + init pose + actuators).
- A **task** (`tasks/velocity/config/<name>/`) registers gym envs and plugs the robot in:
  `self.scene.robot = XHUM1_CYLINDER_CFG.replace(...)` (`.../xhum1/rough_env_cfg.py`).
- Run: `python scripts/rsl_rl/train.py --task=Velocity-Flat-Xhum1-v1 --headless ...` (`README.md`).

## Steps to wire v2.01 into RL

### 1. Place the asset under the RL assets dir
Regenerate the URDF with the RL conventions (free base + `package://` mesh paths) straight into
the walking assets tree, mirroring the v15 layout:
```bash
python scripts/tools/convert_urdf.py \
  --mjcf-file assets/hum2.0_dev_v2.01_20260622/output.xml \
  --urdf-file source/walking/walking/assets/xhum/urdf/v201/humanoid.urdf \
  --remove-world-frame --package xhum/meshes/xhum201
```
Then move the generated `converted_*.stl` to `source/walking/walking/assets/xhum/meshes/xhum201/`
so `package://xhum/meshes/xhum201/...` resolves (mirror `xhum/meshes/xhum15/`).
(The copy in `assets/hum2.0_dev_v2.01_20260622/urdf/` uses `package://converted_*.stl` with no
subdir — it's a self-contained reference; regenerate with `--package` for the RL placement.)

### 2. Create the robot cfg `source/walking/walking/robots/xhum201.py`
Copy `xhum15.py` and change:
- `asset_path` → `.../xhum/urdf/v201/humanoid.urdf`
- `init_state.joint_pos` default angles for the v2.01 joints
- `actuators` groups (legs/feet/waist/arms): every `joint_names_expr` must match v2.01 joint
  names, and each group maps to the right motor constants (step 4).

### 3. ⚠️ Joint/body-name remap (the deferred step — do this first, it gates 2 & 5)
The RL configs assume **G1-style names with a `_joint` suffix** (`.*_hip_pitch_joint`,
`waist_yaw_joint`) and body names like `torso_link` (e.g. height_scanner `prim_path` in
`xhum1/rough_env_cfg.py`). **Our model uses bare names** (`left_hip_roll`, `waist_yaw`, body
`chest_2_01`). Two options:
- **(a) preferred** — add a name-mapping pass in `get_default_config()` (`JointMapping.target_name`
  / `LinkMapping.target_name`) so `output.xml` and the URDF emit the RL names. Keeps the whole
  pipeline reproducible and lets you reuse the v15 configs' regex patterns nearly verbatim.
- (b) rewrite every `joint_names_expr` and body `prim_path` in the v201 configs to the bare names.

### 4. ⚠️ Real MAXON actuators (your PR #191)
`source/walking/walking/robots/actuator_constants.py` holds the ENCOS `EC_*` placeholders
(armature/effort/velocity/stiffness/damping). Replace them — or add a Maxon constant set — from
the Maxon multimodel work, and reference those in the `xhum201.py` actuator groups. Until then,
RL would train on the wrong motor dynamics.

### 5. Create the task `source/walking/walking/tasks/velocity/config/xhum201/`
Mirror `.../xhum1/`: `rough_env_cfg.py`, `flat_env_cfg.py`, `agents/` (PPO runner cfg),
`__init__.py` (gym.register with ids like `Velocity-Flat-Xhum201-v1`). In the env cfgs set
`self.scene.robot = XHUM201_CYLINDER_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")` and update
all body-name references (height_scanner, contact/termination bodies) to v2.01 names.

### 6. Train
```bash
python scripts/rsl_rl/train.py --task=Velocity-Flat-Xhum201-v1 --headless \
  --logger wandb --log_project_name walking_v201 --run_name v201_walk
```

## Gotchas

- **Self-collisions**: `output.xml` carries `<contact><exclude>` for t=0 self-collisions, but URDF
  has no equivalent and the RL cfg sets `enabled_self_collisions=True` (`xhum15.py`). Verify the
  USD self-collision behavior at the rest pose after import.
- **Foot coins**: the URDF holds 12 cylinder collisions per foot-pair, but `UrdfFileCfg` sets
  `replace_cylinders_with_capsules=True` — cylinders become capsules on import. Confirm foot
  contact still behaves as intended.
- **`output.xml` not needed at RL runtime** — it's the source for the URDF/mesh regen only.

## Regenerating the model from scratch (CAD changes)

1. Export (Onshape, **paid** — flag before running): `assets/export_real_mass.py` + `config.json`.
2. Transform: `python assets/robot_xml_cli.py --input assets/hum2.0_dev_v2.01_20260622/robot.xml --output assets/hum2.0_dev_v2.01_20260622/output.xml`
3. URDF: `convert_urdf.py` (step 1 above).

Questions → ping Kevin (model/transformer) or see PR #202.
