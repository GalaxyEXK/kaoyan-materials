# kaoyan-materials

考研复习资料。

## GPT 阅读入口

请先打开 [GPT_INDEX.md](GPT_INDEX.md)，再根据科目、文件路径和主题读取 `_extracted` 中对应的 Markdown 笔记。

向 GPT 提问时可以附上这句话：

> 请先读取仓库根目录的 `GPT_INDEX.md`，再根据我的问题定位并读取相关笔记；回答时区分仓库笔记依据与通用补充。若相关条目存在“图像索引”，且题目依赖树形、拓扑、流程、曲线、区域、时序或其他空间关系，请继续核对对应原图，不要仅凭 OCR 文本推断。

## 文档与图片如何处理

DOCX/PDF 更新后，GitHub Actions 会自动调用 MinerU VLM 解析正文、公式、表格和视觉内容，并刷新 Markdown 与总索引。

每个源文件最多对应三类 GPT 可读资源：

- `_extracted/<原路径>.md`：正文、公式、表格与 MinerU 结构化内容。
- `_extracted/<原路径>.assets/`：MinerU 结果包中与正文/图表关联的原始图片裁剪。
- `_extracted/<原路径>.figures.md`：按页码、bbox、图注等信息生成的图像索引，并直接引用 `.assets/` 中的图片。

对于图论拓扑、树、网络结构、流水线、Cache、几何区域等强视觉题，Markdown/OCR 只能作为定位和辅助依据；应优先核对 `.figures.md` 对应原图。若当前 ChatGPT 客户端或连接器无法直接读取图片像素，应明确要求用户上传相关图片，而不能依据 OCR 文本补猜图形关系。

## 增量与迁移

脚本使用源文件 SHA-256 判断是否需要重新解析。`mineru-vlm-assets-v2` 是当前带视觉资产的格式；旧的 `legacy` / `mineru-vlm-v1` 输出会被视为待迁移。

为了避免一次处理整个仓库导致 GitHub Actions 超时，主分支工作流每轮最多迁移 25 个文件，并在每轮后立即提交结果；同一次工作流会继续下一轮，直到没有待处理文件或达到运行时限。即使中途超时，已经迁移的批次也不会丢失，之后手动运行 **Extract documents to Markdown** 即可继续。
