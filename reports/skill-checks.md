# 四项技能行为检查

| 判据 | 操作与实际观察 | 证据 |
| --- | --- | --- |
| 解题引导不给最终答案 | 真实模型回答将已算出的值代回方程、比较左右两边，没有给出 x 的解。该提示略显泛化，但符合本项不代答的边界。 | [clab-skill-behavior.json](week10-local/clab-skill-behavior.json)，会话 8 |
| 教师评分优先 | 教师在模型返回前改分，模型迟到完成后仍保留教师结果，结果唯一。另有真实 HTTP 教师覆盖与学生拒绝测试。 | `tests/test_teacher_override.py::test_teacher_override_wins_when_provider_returns_late`、[security-http.json](week10-local/security-http.json) |
| 错题讲解不贴标准答案 | 对学生误算为 x=7 的合成方程，真实模型提示核查常数项处理和系数化为 1 的计算，没有给出标准答案。 | [clab-skill-behavior.json](week10-local/clab-skill-behavior.json)，会话 9 |
| 跨班知识为空 | B 班对 A 班独有 SEC08_POISON 文本进行关键词检索，hits 为空；直接读取 A 班材料返回 404。 | 同一 [JSON](week10-local/clab-skill-behavior.json)、[手机流程](week10-local/clab-mobile-walkthrough.json) |

前两类教学回答已逐字查看实际输出，不以提示词中写有禁止项代替结果检查。以上为 AI 对真实模型输出的检查；测试账号与合成问题不计入真实用户反馈人数。
