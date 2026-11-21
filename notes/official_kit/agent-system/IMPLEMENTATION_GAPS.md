# Agent System Implementation Gaps

> 记录 agent-system.zip 替换后，仍需验证或实现的事项。这里记录缺口，不表示这些事项已经完成。

## P0：运行前必须确认

### 1. 官方 loader / schema 兼容性

需要用官方环境验证：

- `skills:` 是否支持在主 Agent 和子 Agent 配置中使用；
- 多个 Skill 是否可以同时加载；
- `!include` 的相对路径如何解析；
- 子 Agent 中的 `instruction: !include ../prompts/*.md` 是否有效；
- Skill 目录中除 `SKILL.md` 外的四个契约模块是否会被加载；
- `agent_tool`、子 Agent 和 Skill 的组合是否能成功编译。

当前仅检查了文件存在和引用路径，尚未通过官方 loader。

### 2. 旧 `system.md` 与新 Project Manager 流程的冲突

`notes/official_kit/submission/prompts/system.md` 仍是旧的单 Agent 修复流程，包含立即定位、立即修改、直接提交等指令。

需要确认官方 harness 是否会自动加载该文件：

- 如果会加载，必须重写或移除与 Project Manager 协作流程冲突的内容；
- 如果不会加载，保留它也必须在文档中明确，避免误用。

### 3. Adapter 配置

参考配置包含：

```yaml
adapter: main_lora
```

以及工具型子 Agent 的：

```yaml
adapter: tool_lora
```

当前新角色配置没有 `adapter` 字段。需要确认：

- 是否必须声明 adapter；
- 主 Agent 和子 Agent 应使用哪个 adapter；
- 缺省 adapter 是否有效；
- 不声明 adapter 是否影响工具调用能力。

## P1：协作机制需要落地

### 4. Agent 间报告的实际传递方式

通信契约定义了以下消息类型：

- `task_assignment`
- `investigation_report`
- `review_feedback`
- `model_change_proposal`
- `diagnosis_update`
- `repair_authorization`
- `repair_report`
- `evaluation_report`

但目前只有格式约定，没有确定报告如何在 Agent 间持久化和传递。

需要确定采用：

- Agent Tool 返回值直接传递；
- 使用官方 `write_file` / `read_file` 写入工作区；
- 或由 Project Manager 将报告整理后注入下一次调用。

如果使用文件，还需确定目录、命名、覆盖/版本规则，并确认这些文件不会被误提交为补丁。

### 5. Repair authorization 的强制规则

需要明确并在 Worker 流程中执行：

- 只有收到明确的 `repair_authorization` 才能编辑源码；
- 授权必须包含 `allowed_scope` 和 `acceptance_criteria`；
- 未授权时只能诊断或复现；
- Checker 拒绝后是否需要重新授权；
- 修复范围改变时是否需要新的授权。

### 6. Project Manager 的调度和返工规则

需要明确：

- 何时调用 Architect、Worker、Checker、Evaluator；
- Architect 诊断后如何创建 Worker 任务；
- Checker 拒绝后如何回到 Architect 或 Worker；
- 最大返工轮数；
- 何时允许 PM 调用 `submit_patch`；
- Evaluator 是否默认调用，还是只在跨任务评估时调用。

目前这些主要写在角色文档中，尚未映射成可执行的调度约束。

## P2：Evaluator 和运行数据

### 7. Evaluator 的跨任务输入

Evaluator 的职责是项目级、跨任务、跨轮次评估，但当前配置没有定义它如何获得：

- 多任务 trace；
- 历史角色报告和模型修订；
- 工具调用次数、token、耗时；
- 重工次数和 Checker 反馈；
- 各任务的最终结果及验证范围。

需要确定数据来源、保存格式、调用时机，并避免让 Evaluator 退化成当前单题的 Checker。

### 8. 端到端最小运行验证

需要使用一个最小本地 Bug 任务验证完整链路：

```text
Project Manager
  -> Architect
  -> Worker
  -> Checker
  -> Project Manager
```

至少检查：

- Architect 不修改源码；
- Worker 先复现和调查；
- Worker 能用证据推翻 Architect；
- Checker 检查模型、证据、根因和补丁，不只是运行测试；
- PM 不替代技术判断；
- 未授权 Worker 不修改源码；
- 报告能够实际传递；
- Evaluator 能读取足够的过程数据。

## P3：提交目录和维护

### 9. 原始设计目录与官方提交目录的边界

当前同时存在：

- `notes/official_kit/agent-system/`：zip 原始设计文档；
- `notes/official_kit/submission/`：转换后的官方提交草稿。

需要明确最终上传入口，并在 README 中说明原始设计目录不是运行配置，避免两套文件被误认为同一入口。

### 10. 最终打包检查

提交前需要检查：

- 只打包官方 submission 需要的文件；
- 不包含本地实验、缓存、工作区报告和大资源；
- 所有 include、skill、sub-agent 引用都能解析；
- 角色 prompt 与 Skill 没有旧版本残留；
- Git 状态和最终压缩包内容一致。

## 当前状态

- 已记录：以上缺口。
- 已完成：从 zip 同步角色、共享契约和角色技能；更新主 Agent 和四个子 Agent 配置。
- 未完成：官方 loader 验证、通信机制落地、授权状态控制、Evaluator 数据接入、端到端运行验证、最终打包。
