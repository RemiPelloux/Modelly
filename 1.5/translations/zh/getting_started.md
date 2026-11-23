# 入门

*本页译自[英文页面](https://remipelloux.github.io/Modelly/getting_started.html)，欢迎指正。*

Modelly 是一个用于构建、分析和可视化基于智能体的模型的模块化框架。

**基于智能体的模型**是一类计算机模拟：多个实体（即智能体）按照为其编写的行为相互作用。智能体可以代表活细胞、动物、个人，甚至整个组织或抽象实体。有时，我们了解系统中各个组成部分的行为，想看看它们的相互作用会在系统层面涌现出怎样的行为和效应。有时，我们对系统的整体行为已有很好的认识，想找出能够解释它的个体行为。又或者，我们想知道如何让智能体最有效地合作或竞争。也可能，我们只是想做一个有许多彩色小点四处移动的有趣玩具。

## 概览

如果想大致了解 Modelly 的功能和结构，请从这里开始：

- [MODELLY 库概览](https://remipelloux.github.io/Modelly/overview.html)：了解 Modelly 的核心概念和组成部分。

## 教程

如果想一步一步学习如何用 Modelly 构建基于智能体的模型，请按照以下教程学习：

- [创建你的第一个模型](https://remipelloux.github.io/Modelly/tutorials/0_first_model.html)：学习如何创建你的第一个 Modelly 模型。
- [AgentSet](https://remipelloux.github.io/Modelly/tutorials/1_agentset.html)：学习如何用 Modelly 的 AgentSet 更有效地管理智能体。
- [智能体激活](https://remipelloux.github.io/Modelly/tutorials/2_agent_activation.html)：学习用 `do`、`shuffle_do` 和 `map` 激活智能体的不同方式，涵盖随机、顺序、同时、分阶段、按类型和条件激活等模式。
- [事件调度](https://remipelloux.github.io/Modelly/tutorials/3_event_scheduling.html)：学习如何在 Modelly 模型中调度事件和管理时间。
- [添加空间](https://remipelloux.github.io/Modelly/tutorials/4_adding_space.html)：学习如何为 Modelly 模型添加空间，并理解 Modelly 的空间架构。
- [收集数据](https://remipelloux.github.io/Modelly/tutorials/5_collecting_data.html)：学习如何用 Modelly 的 DataCollector 收集模型层面和智能体层面的数据。
- [基础可视化](https://remipelloux.github.io/Modelly/tutorials/6_visualization_basic.html)：学习如何用 Modelly 的可视化模块构建交互式仪表板。
- [智能体的动态可视化](https://remipelloux.github.io/Modelly/tutorials/7_visualization_dynamic_agents.html)：学习如何在交互式仪表板中动态呈现你的智能体。
- [使用 SpaceRenderer 进行可视化](https://remipelloux.github.io/Modelly/tutorials/8_visualization_rendering_with_space_renderer.html)：学习如何充分利用 SpaceRenderer 来增强可视化效果。
- [属性层可视化](https://remipelloux.github.io/Modelly/tutorials/9_visualization_property_layer_visualization.html)：学习如何在 Modelly 中可视化属性层。
- [自定义可视化组件](https://remipelloux.github.io/Modelly/tutorials/10_visualization_custom.html)：学习如何为交互式仪表板添加自定义可视化组件。
- [离散事件模拟](https://remipelloux.github.io/Modelly/tutorials/11_discrete_event_simulation.html)：学习如何用 `schedule_event` 构建纯事件驱动的模型，并用排队论加以验证。
- [ABM-DEVS 混合模型](https://remipelloux.github.io/Modelly/tutorials/12_hybrid_abm_devs.html)：学习如何在空间传染病模型中把基于 `step()` 的智能体激活与调度事件结合起来。

## 你自己的项目

- [在你的项目中使用 Modelly](https://remipelloux.github.io/Modelly/using_modelly_in_your_project.html)：从一个空文件夹到一个可复现、经过测量、存放在自己仓库中的模型。
- [创建项目](https://remipelloux.github.io/Modelly/new_project.html)：`modelly new` 生成一个从第一次提交起就设定了随机种子、带有测试并经过检查的项目。
- [Modelly 最佳实践](https://remipelloux.github.io/Modelly/best-practices.html)：使用 Modelly 的技巧和准则概览。

## 课程与领域教程

- [课程](https://remipelloux.github.io/Modelly/course/index.html)：十二次课，带领一个班级从第一个模型走到一项属于自己的、经过验证且可复现的研究。
- [领域教程](https://remipelloux.github.io/Modelly/tutorials/domains/index.html)：每个领域一篇教程，每篇都基于模型库（zoo）中的一个模型。

## 从其他工具迁移

- [从 Mesa 迁移](https://remipelloux.github.io/Modelly/migrating_from_mesa.html)：逐个构造的对照表，以及一个代码改写工具 `python -m modelly.migrate`，它会改写机械性的部分并报告其余部分。
- [从 NetLogo 迁移](https://remipelloux.github.io/Modelly/netlogo.html)：`python -m modelly.netlogo` 把 `.nlogo` 模型转换为可以运行、测试和检查的 Python 模块。
- [从 R 和 Julia 使用](https://remipelloux.github.io/Modelly/r_and_julia.html)：在 R 和 Julia 中读取 Modelly 的 Parquet 结果，并从 R 驱动模型。

## 示例

Modelly 自带一组示例模型。它们都是经典的 ABM，如果你熟悉 ABM 并想快速了解 MODELLY 的工作方式，这些示例是很好的起点。你可以在[这里](https://remipelloux.github.io/Modelly/examples.html)找到它们。

## 更多资源

为了进一步探索 Modelly 及其功能，我们提供以下资源：

### API 文档

- [Modelly API 参考](https://remipelloux.github.io/Modelly/apis/api_main.html)：Modelly 类和函数的详细文档，每个包一页（`modelly.core`、`modelly.space`、`modelly.time`、`modelly.data`、`modelly.behaviour`、`modelly.scenarios`、`modelly.batch`、`modelly.viz`）。

### 源代码与开发

- [Modelly GitHub 仓库](https://github.com/RemiPelloux/Modelly)：获取 Modelly 的全部源代码，参与开发或报告问题。
- [Modelly 发布说明](https://github.com/RemiPelloux/Modelly/releases)：查看 Modelly 的详细更新日志，包括所有历史版本及其功能。

### 社区与支持

- [Modelly GitHub Discussions](https://github.com/RemiPelloux/Modelly/discussions)：参与讨论、提问，并与其他 Modelly 用户交流。

祝你用 Modelly 建模愉快，欢迎随时联系我们！
