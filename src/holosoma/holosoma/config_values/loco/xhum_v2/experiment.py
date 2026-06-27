"""Locomotion experiment presets for xdof xhum_v2 (31 DOF).

注:
- simulator 默认 isaacsim(本地已搭好的环境);可用 CLI `simulator:isaacgym` 覆盖。
- 首版 use_symmetry=False:flip_sign_joint_names/symmetry_joint_names 尚未在仿真里
  逐关节验证,先关对称增强,稳定后再开启验证。
- randomization 复用 g1 的(与机器人无关,按 robot_config 参数化)。
- terrain 用平地,便于新机器人首次冒烟/调试。
"""

from dataclasses import replace

from holosoma.config_types.experiment import ExperimentConfig, NightlyConfig, TrainingConfig
from holosoma.config_values import (
    action,
    algo,
    command,
    curriculum,
    observation,
    randomization,
    reward,
    robot,
    simulator,
    termination,
    terrain,
)

xhum_v2_31dof = ExperimentConfig(
    env_class="holosoma.envs.locomotion.locomotion_manager.LeggedRobotLocomotionManager",
    training=TrainingConfig(project="hv-xhum_v2-manager", name="xhum_v2_31dof_manager"),
    algo=replace(algo.ppo, config=replace(algo.ppo.config, num_learning_iterations=25000, use_symmetry=False)),
    simulator=simulator.isaacsim,
    robot=robot.xhum_v2_31dof,
    terrain=terrain.terrain_locomotion_plane,
    observation=observation.xhum_v2_31dof_loco_single_wolinvel,
    action=action.xhum_v2_31dof_joint_pos,
    termination=termination.xhum_v2_31dof_termination,
    randomization=randomization.g1_29dof_randomization,
    command=command.xhum_v2_31dof_command,
    curriculum=curriculum.xhum_v2_31dof_curriculum,
    reward=reward.xhum_v2_31dof_loco,
    nightly=NightlyConfig(
        iterations=5000,
        metrics={"Episode/rew_tracking_ang_vel": [0.5, "inf"], "Episode/rew_tracking_lin_vel": [0.5, "inf"]},
    ),
)

xhum_v2_31dof_fast_sac = ExperimentConfig(
    env_class="holosoma.envs.locomotion.locomotion_manager.LeggedRobotLocomotionManager",
    training=TrainingConfig(project="hv-xhum_v2-manager", name="xhum_v2_31dof_fast_sac_manager"),
    algo=replace(algo.fast_sac, config=replace(algo.fast_sac.config, num_learning_iterations=50000, use_symmetry=True)),
    simulator=simulator.isaacsim,
    robot=robot.xhum_v2_31dof,
    terrain=terrain.terrain_locomotion_plane,
    observation=observation.xhum_v2_31dof_loco_single_wolinvel,
    action=action.xhum_v2_31dof_joint_pos,
    termination=termination.xhum_v2_31dof_termination,
    randomization=randomization.g1_29dof_randomization,
    command=command.xhum_v2_31dof_command,
    curriculum=curriculum.xhum_v2_31dof_curriculum_fast_sac,
    reward=reward.xhum_v2_31dof_loco_fast_sac,
    nightly=NightlyConfig(
        iterations=50000,
        metrics={"Episode/rew_tracking_ang_vel": [0.6, "inf"], "Episode/rew_tracking_lin_vel": [0.6, "inf"]},
    ),
)

__all__ = ["xhum_v2_31dof", "xhum_v2_31dof_fast_sac"]
