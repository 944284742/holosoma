"""Locomotion action presets for the xhum_v2 robot."""

from holosoma.config_types.action import ActionManagerCfg, ActionTermCfg

xhum_v2_31dof_joint_pos = ActionManagerCfg(
    terms={
        "joint_control": ActionTermCfg(
            func="holosoma.managers.action.terms.joint_control:JointPositionActionTerm",
            params={},
            scale=1.0,
            clip=None,
        ),
    }
)

__all__ = ["xhum_v2_31dof_joint_pos"]
