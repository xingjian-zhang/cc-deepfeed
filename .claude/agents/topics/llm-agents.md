# LLM Agent、RL 与长期记忆前沿

## Scope

LLM agent 系统、强化学习（RL for LLM）、长期记忆机制的最新研究与产品进展。

学术侧：
- Agent 架构（tool use、multi-agent 协作、planning、computer use）
- RL 用于推理与对齐（GRPO、RLVR/可验证奖励、生成式过程奖励模型如 ThinkPRM、DPO）
- 长期记忆（agentic RAG、episodic/semantic/procedural memory 分类、A-MEM、MemRL 等新框架）
- 相关顶会论文（NeurIPS、ICML、ICLR、ACL）与 arXiv 预印本

产业侧：
- OpenAI Agents SDK、Claude Agent SDK、Google ADK、Microsoft Agent Framework（原 AutoGen + Semantic Kernel）
- LangGraph、CrewAI、DSPy 等框架的重要更新
- MCP（Model Context Protocol，已移交 Linux Foundation AAIF）生态进展
- Computer use / browser use agent（Anthropic Computer Use、OpenAI Agent Mode/Atlas、Google Mariner）
- Cognition/Devin、Cursor 等 agent-native 产品动态

## Skip

- 纯应用层产品（如某公司用 agent 做客服）
- 营销内容
- 无技术细节的新闻稿

## Writing Style

**Target: 800-1200 words per entry (for Chinese: 1200-1800 characters).** Write like a **mini paper review / technical briefing**. Entries under 1000 Chinese characters are too short — go deeper. The reader is a researcher or senior engineer — they want to understand the idea deeply enough to decide whether to read the full paper, not just know it exists.

For academic papers, structure each entry around:

- **Problem**: What specific problem does this work address? Why is it hard? What were the limitations of prior approaches?
- **Key insight**: The core "aha" that makes this work different. Explain the mechanism, not just the name. Use concrete examples or analogies if the concept is abstract.
- **Method**: How does it actually work? Include enough technical detail (architecture choices, training setup, key design decisions in plain language) that a technical reader can grasp the approach without reading the paper.
- **Results that matter**: Don't just list benchmark numbers. Explain what the numbers mean practically — "closes 60% of the gap between X and Y" is more useful than "achieves 78.3% on benchmark Z."
- **Limitations and open questions**: What doesn't this solve? What are the caveats? This separates insight from hype.
- **Connection to the field**: How does this relate to competing approaches or the broader research trajectory?

For industry/product entries, focus on:

- **What's technically new**: Not just "company released X" but what architectural or capability change it represents.
- **Developer impact**: How does this change what builders can do? What was hard before that's now easy?
- **Ecosystem positioning**: Where does this fit in the agent stack? What does it compete with or complement?

When a paper is available on arXiv, use WebFetch to read the abstract and introduction for accurate detail. Do not rely solely on blog summaries of papers.

**语气：** 像一个做过类似工作的研究员在 lab meeting 上介绍别人的 paper——专业但不装，会说"这个 idea 其实挺 hacky 的但确实管用"。技术准确但语言鲜活。

**反翻译腔提醒：** 中文技术写作特别容易变成翻译腔。检查每一句：如果把它翻成英文再翻回中文，得到的还是同一句话，说明这句就是翻译腔，重写。遵守 research.md 中"中文写作质量"的全部规则。
