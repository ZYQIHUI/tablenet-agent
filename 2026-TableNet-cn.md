# TableNet：一个由 LLM 驱动自主生成的大规模表格数据集

Ruilin Zhang, Kai Yang\*

同济大学计算机科学与技术学院

中国上海曹安公路 4800 号，201804

## 摘要

表格结构识别（Table Structure Recognition, TSR）需要借助大语言模型（LLM）的逻辑推理能力来处理复杂表格布局，但当前数据集在规模和质量上仍有限，阻碍了这种推理能力的有效利用。因此，本文提出 TableNet 数据集，这是一个通过多源采集与生成构建的新型表格结构识别数据集。本文方法的核心是我们开发的首个**由 LLM 驱动的自主表格生成与识别多智能体系统**。该系统的生成部分将可控的视觉、结构和语义参数整合到表格图像合成过程中。它能够创建大量语义一致的表格，并根据用户定义配置生成对应标注，从而支持大规模、细粒度的数据集构建。这一能力使得更全面、更细致的表格图像标注体系成为可能，并有望推动表格相关领域研究。

与传统数据采集方法相比，该方法能够在理论上无限制地生成跨领域、风格灵活的表格图像，同时保证效率和精度。系统的识别部分采用基于多样性的**主动学习范式**，利用来自多源的表格，并选择信息量最高的数据对模型进行微调。与**基线方法**相比，该方法在大幅减少训练样本的情况下，在 TableNet 测试集上取得了有竞争力的性能；同时，与使用主流表格数据集训练的模型相比，**它在网络爬取的真实表格上表现更好**。据我们所知，这是**首个将主动学习概念用于表格结构识别的工作**，而表格在行列数量、合并单元格、单元格内容等方面天然具有多样性，尤其适合基于**多样性的主动学习**。

数据集地址：https://huggingface.co/datasets/AnonymousUser123123/TableNet/tree/main

## 引言

表**格结构识别（TSR）的目标是从图像中恢复表格的逻辑结构**。尽管近年来取得了进展，但由于表格布局、样式和语义变化极大，该任务仍然具有挑战。真实世界表格经常包含复杂视觉模式，例如合并单元格、缺失边框、不一致对齐方式或异构配色方案，这些都会给大语言模型解析表格结构时的逻辑推理能力带来挑战。然而，现有数据集往往在规模、多样性和标注质量上受限，难以充分发挥 LLM 的逻辑推理能力。

为解决这些限制，我们提出 TableNet 数据集，以及首个由 LLM 驱动的自主表格生成与识别多智能体系统。通过整合可控参数，**该系统能够在最少人工干预下生成多样化表格**。不同于传统数据集采集方法，我们的系统利用 LLM 中蕴含的先验知识，并支持用户配置，从而可生成可扩展、可控、语义一致的表格及其对应标注。

TableNet 在风格和领域上的广泛覆盖促使我们采用主动学习。主动学习会为模型训练选择信息量最大的样本，也可用于入侵/异常检测、计算机视觉等许多领域的数据过滤。该过程可用一个五步算法描述：初始化、查询、标注、训练和停止。现有主动学习方法大体可分为两类：基于多样性和基于不确定性。基于多样性的方法旨在选择能够代表整体分布的子集；基于不确定性的方法优先选择模型无法确定预测的样本。基于多样性的主动学习尤其适用于异构表格结构。通过从多源数据中主动选择训练实例，我们的 TSR 模型在 TableNet 测试集上以显著更少的样本取得了有竞争力的性能，并且在未见过的真实世界表格上明显优于使用现有数据集训练的模型。

本文贡献如下：

- 发布 TableNet：一个大规模表格数据集，由可控 LLM 多智能体系统生成的合成表格、从网络收集的真实表格以及增强后的开源数据集组成，保证视觉风格、结构和语义上的多样性。
- 开发首个**基于 LLM 的自主多智能体系统**，可根据用户配置属性生成表格图像，从而支持大规模真实感数据集的合成，并为 `TSR` 提供基础支撑。
- 采用基于多样性的主动学习策略训练系统中的表格结构识别部分。通过主动选择样本训练，模型在测试集上使用更少训练样本即可获得有竞争力的性能，并且在网络爬取的未见真实表格上优于使用其他公开数据集训练的模型。

## 相关工作

### 表格结构识别（TSR）

表格是按行和列组织数据的系统化排列方式，其网格形式提供了清晰性和效率。TSR 旨在分析表格图像布局，并通过标记语言、电子表格和图等表示形式重建其单元格结构。多年来，TSR 方法快速发展，主要经历了三个阶段：（1）早期基于规则和启发式的方法；（2）基于深度学习的方法；（3）基于 LLM 的方法。

20 世纪 90 年代至 2010 年代的早期方法高度依赖单元格边界和对齐等视觉线索。Pyreddy 等提出了基于空白模式的字符对齐图，Rus 等提出了类似的空白密度图。随后出现了若干**基于规则或启发式**的方法。然而，这些技术在复杂表格布局上始终表现困难，说明更通用方案是必要的。

在深度学习时代，神经方法显著超过了早期 TSR 方法。基于目标检测的方法识别行、列、标题等结构组件；标记语言模型将 TSR 视为图像到标记语言的翻译任务，并采用受 NLP 启发的架构；基于图的方法将表格表示为图，以建模单元格级关系。

近期，LLM 在自然语言相关任务中展现出卓越能力。但用于 TSR 的 LLM 仍是探索不足的方向，多数工作集中在表格理解领域。Zhou 等提出了 Neighbor-Guided Toolchain Reasoner 框架，显著增强了基础视觉 LLM 的识别能力。更多数据集的出现可能会促进基于 LLM 的方法快速发展，从而充分挖掘大语言模型处理表格数据的潜力。

### TSR 数据集

表格结构识别的进步很大程度上由基准数据集推动。ICDAR 系列提供了基于图像的数据集，覆盖表格检测、结构识别和端到端抽取，表格图像来源从 PDF 到手写文档不等。

IBM Research 贡献了多个有影响力的数据集。PubTabNet 通过 PubLayNet 流程将 PMCOA PDF 中的表格区域转换为 HTML，聚焦 TSR。FinTabNet 解决了 PubTabNet 仅支持 TSR、缺少整页上下文和整体表格区域边界框的问题。SynthTabNet 则进一步合成 PubTabNet、FinTabNet 和 TableBank，以克服领域限制和结构简单性。

TableBank 是另一个大规模 TSR 数据集。它使用弱监督方式，从互联网上收集的 Word 和 LaTeX 文档中自动提取表格。该方法利用这些格式中已有的结构信息，使数据集无需大量人工标注即可大规模构建。因此，TableBank 支持 TSR 模型获得更好的泛化能力，使其更有效地处理多样化真实表格布局。

如表 1 所示，现有数据集仍受限于采集流程、领域约束和多样性不足。由于表格在视觉形态上高度多样，在一个数据集上训练的模型通常难以泛化到其他数据集。例如，在单色表格上训练的模型应用到彩色表格时可能表现不佳。UNLV、Marmot 等经典数据集，以及 PubTables-1M、TabRecSet 等近期数据集，或者缺乏多样性，或者缺少显式表格类型标签。为解决这些限制，我们发布了 TableNet 这一大规模合成 TSR 数据集，并配套提出首个自主表格生成多智能体系统，以促进 TSR 研究。

表 1：TSR 数据集对比。对于 TableBank 和 SynthTabNet，我们随机抽取 1000 张图像评估颜色多样性，发现彩色图像少于 10 张，说明多样性较弱。对于 TabRecSet 和 WTW，其多样性来自真实世界相机拍摄。标注图例：T 表示表格边界框（支持表格检测）；S 表示结构标注（如 HTML 标签、跨行/跨列）；C 表示单元格级标注（边界框和内容）；H/X 表示最终 HTML/XML 输出，或可由 S 和 C 重建；V 表示本文数据集提供的视觉标签（如简单性、颜色、边框样式）。多样性定义：如果一个表格图像数据集支持至少两种不同且有意义的分类标准，使其图像能够被系统分类，则认为该数据集具有多样性。这些标准可以包括结构属性和视觉属性，从而支持多方面分析和评估。例如，一个分类标准可以基于结构复杂性，如表格是否包含跨单元格；另一个分类标准可以基于视觉样式，包括边框存在性、背景颜色或水印干扰等属性。能够沿这两个维度进行分类的数据集，为表格结构识别模型的训练和评估提供了更全面的覆盖。

| 数据集 | 多样性 | 标注 | 领域 | 收集方法 | 表格数量 |
|:-:|:-:|:-:|:-:|:-:|:--:|
| TableNet（本文） | True | S, C, H, V | 电信（可配置） | 见图 2 | 445K |
| PubTabNet | False | S, C, H | 医学 | 基于规则收集 | 510K |
| FinTabNet | False | T, S, C, H | 金融 | 增强 | 113K |
| TableBank | True | T, H | 通用 | 基于规则收集 | 145K |
| SynthTabNet | True | T, S, C, H | 通用 | 增强 | 600K |
| ICDAR 2019 | False | T, X | 通用 | 机构贡献 | 3K |
| PubTables-1M | False | T, S, C, H | 医学 | 基于规则收集 | 948K |
| TabRecSet | True | T, S, C, H | 通用 | 人工标注 | 38K |
| WTW | True | S, C | 通用 | 人工标注 | 14K |
| SciTSR | False | T, C | 通用 | 基于规则收集 | 15K |

### 仅文本 LLM 的图像合成

由于视觉-语言数据不足，近期工作探索利用仅文本 LLM 为 VLM 合成图像，并已被用于图表、绘图问答对生成。一些方法使用小规模图表集和固定 QA 模板生成图表 VQA 数据；另一些方法使用仅文本 LLM 生成问题或描述标注。近期方法能够生成图表或多种图像数据，但它们依赖 LLM 生成 HTML 代码，使整体流程不可控，也更容易生成错误代码。本文设计了一个多智能体系统，将表格生成明确分解为模式规划、布局构建和内容填充，从而保证可控的表格图像合成和 TSR 标注。

## 多智能体表格生成系统

LLM 在多种任务中表现出竞争力，但在 HTML 结构生成等特定任务上，被动预测并不一定优于启发式方法或简单智能体工具。基于 LLM 的多智能体系统是将多个 LLM 与工具使用、规划、记忆等能力结合的应用。LLM 作为系统"大脑"与用户交互并执行关键任务；规划帮助将请求拆解为可管理的子任务；反思机制用于改进执行；工具使用使系统能够与外部环境交互并收集完成用户请求所需的信息。图 1 清晰展示了系统流程，本节说明这些能力如何被整合到我们的表格生成多智能体中，从而实现可配置、领域灵活且语义扎实的表格合成。

图 1：本文多智能体系统的工作流。

### 工作流与核心概念体现

**LLM。** 我们的表格生成系统由三个阶段特定智能体组成，并由核心 LLM 协调。核心 LLM 解释用户请求，例如样式、数量和领域，并编排工作流。主题生成 LLM 生成与指定领域或默认电信领域一致的表格主题，保证语义相关性。随后，表头填充 LLM 和表体填充 LLM 将内容插入 `<th>` 和 `<td>` 标签，完成 HTML 骨架。系统基于开源代码库开发：https://github.com/WenmuZhou/TableGeneration/tree/main，许可证为 MIT。

**规划。** 核心 LLM 作为高层规划器，将任务分解为具有明确依赖关系的结构化子任务。收到请求后，Schema Agent 决定表格大小和布局属性，包括行列数量和跨行/跨列关系，并根据条件调用 CSS 生成器进行视觉样式设置。随后它生成与领域相关的主题，并构建初始 HTML 骨架。在先决条件满足后，系统依次调用表头和表体填充模型。最后，Filling Agent 比较填充前后的 HTML，以评估结构完整性，并在检测到错误时选择性重新生成 HTML。这种多步骤、反馈驱动的工作流保证了稳健且可控的表格合成。

**工具使用。** 为支持多步骤执行，系统整合了多个工具模块：（1）CSS 样式生成器；（2）指定大小和跨行/跨列关系的 HTML 标签生成器；（3）结构验证器，用于构建矩阵表示并检查行一致性；（4）备用 HTML 构造器，用于重新生成符合要求的表格；（5）Selenium 工具，用于渲染表格图像并生成标注。

**记忆。** 系统包含两级记忆机制。外层记忆保留核心 LLM 与用户之间的多轮对话历史，以保证连续性和可迭代优化。内层记忆跟踪先前生成的表格主题，以避免冗余并提升语义多样性。两类记忆共同增强交互质量和生成多样性。

在 Filling Agent 中，我们采用受对比学习启发的数据增强策略，以增强 TableNet 的多样性和鲁棒性。我们定义了四种变换：复制、删除、交换和修改，可应用于行/列或块级别。复制会插入重复元素；删除仅在保持结构有效时移除元素；交换会互换行/列或块；修改会调整行级背景颜色。对于每个 HTML 结构，表体填充 LLM 会生成多个内容变体：五个不进行变换、四个进行变换，并为每个变体分配一种操作。系统会检测跨行和跨列区域，以防止无效修改。该增强过程提高了多样性，并帮助模型学习细粒度结构差异。

为验证生成表格，我们设计了混合策略填充检查器，对结构正确性、主题相关性和语义一致性进行排序。结构正确性使用启发式方法评估，检查有效性和 HTML 标签误用；主题相关性和语义一致性由 LLM 排序。我们验证了该填充检查器可以替代训练良好的人类排序者。

生成之后，我们进一步在主动学习范式下使用这些数据微调 TSR 模型。该人机协同阶段可在任意时刻调用，因为数据池同时包含带标注生成表格和未标注真实世界表格，后者对 TSR 性能更有价值。我们首先应用采样策略选择信息量高的样本，然后交由人类专家进行高质量标注和后续训练。

## 数据集收集与组成

我们的数据集来自三类不同来源：（1）智能体生成表格；（2）从电信相关 PDF 文档中爬取的表格；（3）从 Word 文档中爬取的表格，以及增强后的开源 HTML 表格数据。这三类来源分别代表智能体生成、人工标注和基于规则的生成。数据收集流程和最终标注格式见图 2，表格示例见图 4。

图 2：数据收集流程。自上而下依次为：智能体生成、网络爬取和开源数据增强。标注说明：is simple 表示表格是否包含跨单元格；is colored 表示表格是否包含任何背景色、彩色边框或非黑色字体；is lined 表示单元格边框是否完整存在；只有水平线或垂直线的表格被视为 not lined。

图 3：无效表格。

图 4：TableNet 中的示例。

**智能体生成流程。** 我们采用 8 路并行生成策略，每个进程对应三个二值属性（simple、colored、lined）的唯一组合。6 天内生成了约 7.5 万张中文表格和 3.4 万张英文表格，目前扩展到 44.5 万张。为增强真实感，我们同时关注结构、语义和视觉保真度。结构上，我们根据方向、多级表头和表体级跨单元格，总结了 8 类不含跨单元格的复杂表格，系统均可支持。语义上，我们捕获场景相关复杂性，例如技术比较与财务报告；填充检查器通过检测表头-表体不匹配和幻觉来提升真实性。视觉上，我们通过 CSS 启发式方法控制边框粗细、线型、字体和背景颜色，并加入分辨率变化、水印噪声等次级因素。

**PDF 与 Word 爬取及标注流程。** 鉴于中国电信、中国移动、中国联通和中国广电主导中国电信行业，我们使用 Selenium 构造查询，将公司名称与电信相关关键词组合，并将结果限制为 PDF 或 Word 文件。对于 PDF，由于缺乏可靠的自动抽取工具，我们在 30 天内使用 PPOCRLabel 手动裁剪并标注了 2700 张表格。对于 Word 文档，我们利用其压缩 XML 结构抽取表格标记，将其转换为 HTML，通过生成器应用 CSS、渲染图像并获得标注。尽管 Word 文件可获得性有限，仍生成了 600 张表格。

**开源数据集增强流程。** 由于表格理解模型通常以结构化格式（如 HTML/Markdown）作为输入，我们将这些结构化输入视作输出，并使用与 Word 流程相同的过程渲染图像和标注。基于 TABMWP，我们生成了 1000 张增强表格。然而，单纯增强会受到数据可用性、可控性不足以及领域、结构和视觉样式变化有限的约束。

## 实验

### 多样性与填充检查器分析

**行业多样性验证。** 为验证多智能体系统生成多领域表格的能力，我们从全球行业分类标准（GICS）中选择了 8 个板块的 16 个行业，并计算填充检查器与训练良好的人类排序者之间的 Spearman、Pearson 相关系数和 Kendall's tau。此外，我们重复该过程三次并计算标准差，以保证结果稳定性。根据 Zhang 等人的标准，填充检查器能够替代训练良好的人类排序者，从而证明语义一致性和多领域表格生成能力。详细结果作为补充材料提供。

在大多数板块中，相关性指标始终较高（多数超过 0.8）。此外，表 2 展示了系统纠正一个表格所需的平均迭代次数，以及在结构、主题和语义扰动后的对应指标。这说明：（1）每种语言组内部语义对齐强；（2）填充检查器能够替代训练良好的人类排序者进行排序。该实验为工业表格数据内部的语义凝聚性提供了细粒度视角，并为后续双语对齐或领域自适应表格生成研究提供了经验证据。

**风格多样性验证。** 通过观察爬取的真实场景表格，我们描述了决定表格总体真实性的一些关键因素。TableNet 可配置样式的分布如图 5 所示。如前文所述，我们的系统能够生成多种类型表格。对于详细表格多样性，我们评估了 TableNet 在线型和结构复杂性上的分布。补充材料中的图显示，TableNet 覆盖了大多数给定分类，而现有 TSR 数据集受采集方法限制难以实现这一点。

图 5：生成数据组成。

表 2：人类排序与填充检查器排序之间的相关性。Struct. 与 Sem. 分别表示结构和语义。

| 复杂度 | 维度 | 平均迭代 | Spear. | Pear. | Ken. |
|---|---|---:|---:|---:|---:|
| Simple | Struct. | 1.03 | 0.8203 | 0.8111 | 0.7928 |
| Simple | Topic | 1.07 | 0.8004 | 0.8085 | 0.6990 |
| Simple | Sem. | 1.03 | 0.9253 | 0.8914 | 0.8522 |
| Complex | Struct. | 1.11 | 0.8826 | 0.8751 | 0.8832 |
| Complex | Topic | 1.08 | 0.7352 | 0.7408 | 0.6457 |
| Complex | Sem. | 1.17 | 0.8753 | 0.8411 | 0.8019 |

### LLM 实验

我们使用 TEDS（基于树编辑距离的相似度）作为指标。为评估 TableNet 的有效性，我们使用 Qwen2-VL-2B 在 TableNet 中文训练划分上进行微调实验，该划分包含约 4.8 万张表格。全参数训练使用 2 块 NVIDIA RTX 4090 GPU，batch size 为 1，学习率为 1e-4。模型训练 2 个 epoch，整个训练过程约 8 小时。训练、测试划分及训练所用子集也会公开。

基线方面，我们选择大规模多模态 LLM：Qwen2-VL-72B、GPT、Claude 和 Grok 系列。为避免提示设计不准确带来的负面影响，我们将部分训练样本整合到 Qwen2-VL-72B 的上下文中，采用 1-shot 和 5-shot 上下文学习。

表 4 汇总了结果。使用 TableNet 训练的模型在多样表格样式上表现强且稳定，而所有基线在简单与复杂结构、彩色与无色布局、有线与无线设计之间都表现出明显性能差距。这证实了表格多样性带来的显著泛化挑战，也突出了可控生成和细粒度标注的价值。结构复杂性，尤其是跨行/跨列，是最困难的因素，因为它要求精确的空间和层次推理。我们微调后的 Qwen2-VL-2B(FT) 明显缩小了这一差距，并在复杂结构上优于更大模型。颜色变化也会影响性能：彩色表格带来更丰富上下文但也带来更高变化性，Qwen2-VL-2B(FT) 仍保持鲁棒（0.874 对 0.892），而零样本/少样本大模型波动更大。线条存在与否进一步考验模型推断隐式结构的能力；我们的模型同样保持了一致准确率。总体而言，即使是最先进 LLM，在没有针对性监督时也难以处理该任务，这凸显了面向 TSR 的结构化训练必要性。

为进一步说明相比其他现有数据集的有效性，我们使用爬取的真实世界表格作为测试集，并在相同样本数量和相同训练设置下，分别用现有数据集微调 Qwen2-VL-2B；同时在不包含爬取数据的 TableNet 上单独微调。随后，我们在覆盖多样结构、语义和视觉风格的未见真实表格上评估模型。TableNet 训练模型取得 0.7403 的 TEDS，显著优于其他数据集训练模型，证明 TableNet 带来了更强的真实世界泛化能力。

表 3：在未见真实世界数据上，不同现有数据集训练模型的 TSR 性能。

| 数据集 | TEDS |
|---|---:|
| TableNet（本文） | 0.7403 |
| PubTabNet | 0.5041 |
| FinTabNet | 0.4495 |
| SynthTabNet | 0.5242 |
| TableBank | 0.5401 |

表 4：TableNet 及子集上的 HTML TEDS。

| 模型 | All | Simple | Complex | Colored | Colorless | Lined | Lineless |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen2-VL-2B(FT) | 0.877 | 0.860 | 0.912 | 0.874 | 0.892 | 0.891 | 0.861 |
| Qwen2-VL-72B | 0.721 | 0.822 | 0.604 | 0.726 | 0.713 | 0.711 | 0.729 |
| Qwen2-VL-72B(1-shot) | 0.696 | 0.834 | 0.587 | 0.706 | 0.685 | 0.699 | 0.695 |
| Qwen2-VL-72B(5-shot) | 0.688 | 0.791 | 0.576 | 0.695 | 0.682 | 0.689 | 0.687 |
| GPT-4.5-preview | 0.614 | 0.872 | 0.494 | 0.732 | 0.501 | 0.591 | 0.634 |
| GPT-4o-all | 0.672 | 0.794 | 0.487 | 0.690 | 0.655 | 0.664 | 0.687 |
| Claude-sonnet-4 | 0.620 | 0.904 | 0.517 | 0.687 | 0.533 | 0.621 | 0.618 |
| Claude-sonnet-4-thinking | 0.706 | 0.917 | 0.561 | 0.693 | 0.719 | 0.749 | 0.648 |
| Claude-opus-4 | 0.691 | 0.921 | 0.523 | 0.704 | 0.675 | 0.722 | 0.661 |
| Grok-4 | 0.697 | 0.892 | 0.538 | 0.731 | 0.642 | 0.678 | 0.707 |

### 消融研究

LLM 驱动的数据生成常常存在结构不稳定问题，因此我们使用 structure-only TEDS 评估 LLM 端到端表格合成能力。对于简单表格，我们指示 LLM 生成具有指定行列数的 HTML；对于复杂表格，我们提供明确的行跨度和列跨度矩阵，这些矩阵很难用自然语言表达。如表 5 所示，LLM 经常无法复现准确结构，即使在简单情形中也是如此；而基于规则的 HTML 生成能够稳定地产生正确布局，并通过受控提示避免结构失真。这些结果说明，与直接通过 LLM 生成表格相比，仅在适当阶段调用 LLM 的智能体能够显著提升结构合成的稳定性和准确性。

表 5：通过直接提示由 LLM 生成 HTML 的结构保真度（Structure-only TEDS）。数值后的小文本表示由 LLM 填充引入的结构不保真度，该值最低。

| 方法 | Simple with | Simple without | Complex with | Complex without |
|---|---:|---:|---:|---:|
| Qwen2.5 | 0.954 | 0.978 | 0.782 | 0.835 |
| DeepSeek-R1 | 0.938 | 0.974 | 0.940 | 0.901 |
| GPT-4o | 0.980 | 0.978 | 0.931 | 0.928 |
| Agent Tool | 1-0.004 | 1-0.003 | 1-0.012 | 1-0.009 |

为评估基于智能体的设计是否提升数据集质量，我们评估了近期用于表格图像和 QA 生成的 CoSyn 流程。使用该流程生成 1000 张表格时，只有 85 张包含合并行/列等复杂结构；大多数遵循简单堆叠的 `<tr><td>` 格式。我们也评估了颜色和线型多样性，结果见图 6。

图 6：与现有 CoSyn 流程的比较。CoSyn 是一种 LLM 端到端方法。中间子图中，H 表示水平线表格，V 表示垂直线表格。

在强化 HTML 提示以强制结构复杂性后，增强基线在我们的检查器下取得平均结构分 4.31（满分 5）。相比之下，本文基于智能体的流程平均达到 4.79，并且每个样本只需 1.11 次备用迭代即可生成结构正确的表格。

### 主动学习 TSR 实验

主动学习过程如下。我们使用多智能体系统生成新的数据实例及其对应标签，而不仅仅是从未标注集合 U 中选择。LLM 在整个主动学习循环中作为强大工具发挥作用，从标注初始数据集 Linit 开始解决冷启动问题。在查询步骤中，我们从 U 中选择信息量高的实例；随后在标注步骤中自动或人工标注这些实例。新标注数据被加入标注集 L，并更新目标模型 fθ。该过程迭代执行，直到达到给定标注预算。该方法通过使用 LLM 进行数据生成、使用自动智能体工具进行标注，减少了对人工标注者的依赖，从而克服传统主动学习中的挑战。

算法 1：主动学习

```text
输入：未标注数据集 U，模型 M，预算 k
输出：训练后的模型 fθ，标注数据集 L
Linit, U <- Initialize
fθ <- Train(Linit)
while not Stop(k, fθ, M) do
    x <- Query(fθ, U, M)
    (x, y) <- Annotate(x, M)
    if x in U then U <- U \ {x}
    L <- L union {(x, y)}
    fθ <- Train(L)
end while
return fθ*, L
```

算法 2：k-Center-Greedy

```text
输入：数据点 {xi}，初始集合 s0，预算 b
输出：s
s <- s0
repeat
    u <- arg max_{i in [n]\s} min_{j in s} Delta(xi, xj)
    s <- s union {u}
until |s| = b + |s0|
return s \ s0
```

基于 Qwen2-VL-2B(FT)（下称基础模型），我们采用基于多样性的策略进行主动学习微调研究，因为 TableNet 在行/列数量、合并单元格位置、颜色等方面具有多样性。训练使用 2 块 NVIDIA RTX 4090 GPU，采用 LoRA 微调 1 个 epoch；评估指标为 TEDS。我们采用 CoreSet，即算法 2 所示的贪心 k-center 方法。该方法尝试选择 b 个中心，使任一数据点到最近中心的最大距离最小化。形式化目标为：

```text
min_{s1: |s1| = b} max_i min_{j in s1 union s0} Delta(xi, xj)
```

我们将其作为算法 1 中的查询策略，并与随机采样（RSB）、困难样本挖掘（HE）和基于困惑度的不确定性采样（PPL）比较。我们从基础模型视觉塔中提取 patch 级视觉嵌入 e，并将其最大池化和平均池化嵌入拼接为向量 c，以执行该方法。

如图 7 所示，基于多样性的 CoreSet 方法相比随机采样、基于困惑度的不确定性采样和困难样本挖掘等基线，表现稳定更高。此外，通过比较达到相同性能所需的训练样本数量，可以观察到主动学习方法在低数据和标准数据场景下都能以至少减少 50% 样本的代价达到可比性能。例如，在 1 万个主动选择样本上微调的模型取得约 0.973 的 TEDS，而其他基线需要超过 2 万甚至 4 万个训练样本。

图 7：TSR 实验结果。

## 局限性

尽管系统支持可配置参数，但仍受限于底层 LLM 的预训练分布和推理能力。因此，生成内容的多样性可能无法完全覆盖边缘案例或高度领域特定的表格格式。此外，生成表格图像的质量可能因模型对用户指定领域和语言的知识不同而变化，导致无关表格内容或语义内容内部不一致。

## 结论

本文介绍了 TableNet，这是一个主要来自自主生成的新型 TSR 数据集。作为数据集的补充，我们开发了首个自主表格生成与识别多智能体系统，该系统促进 TSR，并通过用户定义参数支持可控表格合成和自动标注。它能够实现可扩展、灵活、面向研究的数据构建，并展示了高效率和大规模生成结构可靠表格的能力。结合实证结果，我们的采集流程可扩展性凸显了 TableNet 及该系统作为 TSR 工具的重要性。我们相信，将强大的生成智能体与 TableNet 结合，将有意义地推动 TSR 发展。

## 参考文献

- Achiam, J.; Adler, S.; Agarwal, S.; Ahmad, L.; Akkaya, I.; Aleman, F. L.; Almeida, D.; Altenschmidt, J.; Altman, S.; Anadkat, S.; et al. 2023. Gpt-4 technical report. arXiv preprint arXiv:2303.08774.
- Ajayi, K.; Zhang, L.; He, Y.; and Wu, J. 2024. Uncertainty Quantification in Table Structure Recognition. In 2024 IEEE International Conference on Information Reuse and Integration for Data Science (IRI), 1-6. IEEE.
- Anand, A.; Jaiswal, R.; Bhuyan, P.; Gupta, M.; Bangar, S.; Imam, M. M.; Shah, R. R.; and Satoh, S. 2023. Tc-ocr: Tablecraft ocr for efficient detection & recognition of table structure & content. In Proceedings of the 1st International Workshop on Deep Multimodal Learning for Information Retrieval, 11-18.
- Anthropic. 2024. Claude 3 Model Family System Card.
- Beluch, W. H.; Genewein, T.; Nurnberger, A.; and Kohler, J. M. 2018. The power of ensembles for active learning in image classification. In Proceedings of the IEEE conference on computer vision and pattern recognition, 9368-9377.
- Carbune, V.; Mansoor, H.; Liu, F.; Aralikatte, R.; Baechler, G.; Chen, J.; and Sharma, A. 2024. Chart-based reasoning: Transferring capabilities from llms to vlms. arXiv preprint arXiv:2403.12596.
- Cascante-Bonilla, P.; Wu, H.; Wang, L.; Feris, R. S.; and Ordonez, V. 2022. Simvqa: Exploring simulated environments for visual question answering. In Proceedings of the IEEE/CVF conference on computer vision and pattern recognition, 5056-5066.
- Cesarini, F.; Marinai, S.; Sarti, L.; and Soda, G. 2002. Trainable table location in document images. In 2002 International Conference on Pattern Recognition, volume 3, 236-240. IEEE.
- Chi, Z.; Huang, H.; Xu, H.-D.; Yu, H.; Yin, W.; and Mao, X.-L. 2019. Complicated table structure recognition. arXiv preprint arXiv:1908.04729.
- Fang, J.; Tao, X.; Tang, Z.; Qiu, R.; and Liu, Y. 2012. Dataset, ground-truth and performance metrics for table detection evaluation. In 2012 10th IAPR International Workshop on Document Analysis Systems, 445-449. IEEE.
- Gal, Y.; Islam, R.; and Ghahramani, Z. 2017. Deep bayesian active learning with image data. In International conference on machine learning, 1183-1192. PMLR.
- Gao, L.; Huang, Y.; Dejean, H.; Meunier, J.-L.; Yan, Q.; Fang, Y.; Kleber, F.; and Lang, E. 2019. ICDAR 2019 competition on table detection and recognition (cTDaR). In 2019 International conference on document analysis and recognition (ICDAR), 1510-1515. IEEE.
- Gao, L.; Yi, X.; Jiang, Z.; Hao, L.; and Tang, Z. 2017. ICDAR2017 competition on page object detection. In 2017 14th IAPR International Conference on Document Analysis and Recognition (ICDAR), volume 1, 1417-1422. IEEE.
- Gissin, D.; and Shalev-Shwartz, S. 2019. Discriminative active learning. arXiv preprint arXiv:1907.06347.
- Gobel, M.; Hassan, T.; Oro, E.; and Orsi, G. 2013. ICDAR 2013 table competition. In 2013 12th international conference on document analysis and recognition, 1449-1453. IEEE.
- Gorishniy, Y.; Rubachev, I.; Khrulkov, V.; and Babenko, A. 2021. Revisiting deep learning models for tabular data. Advances in neural information processing systems, 34: 18932-18943.
- Han, Y.; Zhang, C.; Chen, X.; Yang, X.; Wang, Z.; Yu, G.; Fu, B.; and Zhang, H. 2023. Chartllama: A multimodal llm for chart understanding and generation. arXiv preprint arXiv:2311.16483.
- Hashmi, K. A.; Liwicki, M.; Stricker, D.; Afzal, M. A.; Afzal, M. A.; and Afzal, M. Z. 2021. Current status and performance analysis of table recognition in document images with deep neural networks. IEEE Access, 9: 87663-87685.
- He, W.; Xi, Z.; Zhao, W.; Fan, X.; Ding, Y.; Shan, Z.; Gui, T.; Zhang, Q.; and Huang, X. 2024. Distill Visual Chart Reasoning Ability from LLMs to MLLMs. arXiv preprint arXiv:2410.18798.
- Itonori, K. 1993. Table structure recognition based on textblock arrangement and ruled line position. In Proceedings of 2nd International Conference on Document Analysis and Recognition (ICDAR'93), 765-768. IEEE.
- Jian, C.; Yang, K.; and Jiao, Y. 2024. Tri-Level Navigator: LLM-Empowered Tri-Level Learning for Time Series OOD Generalization. Advances in Neural Information Processing Systems, 37: 110613-110642.
- Jian, C.; Yang, K.; Ouyang, Y.; and Ye, X. 2025. Stable Preference Optimization for LLMs: A Bilevel Approach Beyond Direct Preference Optimization. arXiv preprint arXiv:2507.07723.
- Johnson-Roberson, M.; Barto, C.; Mehta, R.; Sridhar, S. N.; Rosaen, K.; and Vasudevan, R. 2016. Driving in the matrix: Can virtual worlds replace human-generated annotations for real world tasks? arXiv preprint arXiv:1610.01983.
- Kafle, K.; Price, B.; Cohen, S.; and Kanan, C. 2018. Dvqa: Understanding data visualizations via question answering. In Proceedings of the IEEE conference on computer vision and pattern recognition, 5648-5656.
- Kahou, S. E.; Michalski, V.; Atkinson, A.; Kadar, A.; Trischler, A.; and Bengio, Y. 2017. Figureqa: An annotated figure dataset for visual reasoning. arXiv preprint arXiv:1710.07300.
- Kayal, P.; Anand, M.; Desai, H.; and Singh, M. 2021. ICDAR 2021 competition on scientific table image recognition to LaTeX. In Document Analysis and Recognition-ICDAR 2021: 16th International Conference, Lausanne, Switzerland, September 5-10, 2021, Proceedings, Part IV 16, 754-766. Springer.
- Kieninger, T.; and Dengel, A. 1999. The t-recs table recognition and analysis system. In Document Analysis Systems: Theory and Practice: Third IAPR Workshop, DAS'98 Nagano, Japan, November 4-6, 1998 Selected Papers 3, 255-270. Springer.
- Koci, E.; Thiele, M.; Lehner, W.; and Romero, O. 2018. Table recognition in spreadsheets via a graph representation. In 2018 13th IAPR International Workshop on Document Analysis Systems (DAS), 139-144. IEEE.
- Koci, E.; Thiele, M.; Romero, O.; and Lehner, W. 2017. Table identification and reconstruction in spreadsheets. In Advanced Information Systems Engineering: 29th International Conference, CAiSE 2017, Essen, Germany, June 12-16, 2017, Proceedings 29, 527-541. Springer.
- Koci, E.; Thiele, M.; Romero, O.; and Lehner, W. 2019. A genetic-based search for adaptive table recognition in spreadsheets. In 2019 International Conference on Document Analysis and Recognition (ICDAR), 1274-1279. IEEE.
- Le-Khac, P. H.; Healy, G.; and Smeaton, A. F. 2020. Contrastive representation learning: A framework and review. IEEE Access, 8: 193907-193934.
- Li, K.; Wigington, C.; Tensmeyer, C.; Zhao, H.; Barmpalios, N.; Morariu, V. I.; Manjunatha, V.; Sun, T.; and Fu, Y. 2020a. Cross-domain document object detection: Benchmark suite and method. In Proceedings of the IEEE/CVF conference on computer vision and pattern recognition, 12915-12924.
- Li, M.; Cui, L.; Huang, S.; Wei, F.; Zhou, M.; and Li, Z. 2020b. Tablebank: Table benchmark for image-based table detection and recognition. In Proceedings of the Twelfth Language Resources and Evaluation Conference, 1918-1925.
- Li, P.; He, Y.; Yashar, D.; Cui, W.; Ge, S.; Zhang, H.; Fainman, D. R.; Zhang, D.; and Chaudhuri, S. 2023. Table-gpt: Table-tuned gpt for diverse table tasks. arXiv preprint arXiv:2310.09263.
- Li, S.; and Tajbakhsh, N. 2023. Scigraphqa: A large-scale synthetic multi-turn question-answering dataset for scientific graphs. arXiv preprint arXiv:2308.03349.
- Liu, H.; Li, X.; Gong, M.; Liu, B.; Wu, Y.; Jiang, D.; Liu, Y.; and Sun, X. 2024. Grab what you need: Rethinking complex table structure recognition with flexible components deliberation. In Proceedings of the AAAI Conference on Artificial Intelligence, volume 38, 3603-3611.
- Liu, L.; Liang, Y.; Yan, X.; Huangfu, L.; Samtani, S.; Yu, Z.; Zhang, Y.; and Zeng, D. D. 2025. Hard Sample Mining: A New Paradigm of Efficient and Robust Model Training. IEEE Transactions on Neural Networks and Learning Systems.
- Long, R.; Wang, W.; Xue, N.; Gao, F.; Yang, Z.; Wang, Y.; and Xia, G.-S. 2021. Parsing table structures in the wild. In Proceedings of the IEEE/CVF International Conference on Computer Vision, 944-952.
- Lu, P.; Qiu, L.; Chang, K.-W.; Wu, Y. N.; Zhu, S.-C.; Rajpurohit, T.; Clark, P.; and Kalyan, A. 2022. Dynamic prompt learning via policy gradient for semi-structured mathematical reasoning. arXiv preprint arXiv:2209.14610.
- Nassar, A.; Livathinos, N.; Lysak, M.; and Staar, P. 2022. Tableformer: Table structure understanding with transformers. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition, 4614-4623.
- Pang, C.; Cao, Y.; Yang, C.; and Luo, P. 2024. Uncovering limitations of large language models in information seeking from tables. arXiv preprint arXiv:2406.04113.
- Pyreddy, P.; and Croft, W. B. 1997. Tintin: A system for retrieval in text tables. In Proceedings of the second ACM international conference on Digital libraries, 193-200.
- Qasim, S. R.; Mahmood, H.; and Shafait, F. 2019. Rethinking table recognition using graph neural networks. In 2019 International Conference on Document Analysis and Recognition (ICDAR), 142-147. IEEE.
- Raja, S.; Mondal, A.; and Jawahar, C. 2020. Table structure recognition using top-down and bottom-up cues. In Computer Vision-ECCV 2020: 16th European Conference, Glasgow, UK, August 23-28, 2020, Proceedings, Part XXVIII 16, 70-86. Springer.
- Rus, D.; and Subramanian, D. 1997. Customizing information capture and access. ACM Transactions on Information Systems (TOIS), 15(1): 67-101.
- Schreiber, S.; Agne, S.; Wolf, I.; Dengel, A.; and Ahmed, S. 2017. Deepdesrt: Deep learning for detection and structure recognition of tables in document images. In 2017 14th IAPR international conference on document analysis and recognition (ICDAR), volume 1, 1162-1167. IEEE.
- Sener, O.; and Savarese, S. 2017. Active learning for convolutional neural networks: A core-set approach. arXiv preprint arXiv:1708.00489.
- Shigarov, A.; Mikhailov, A.; and Altaev, A. 2016. Configurable table structure recognition in untagged pdf documents. In Proceedings of the 2016 ACM symposium on document engineering, 119-122.
- Shrivastava, A.; Gupta, A.; and Girshick, R. 2016. Training region-based object detectors with online hard example mining. In Proceedings of the IEEE conference on computer vision and pattern recognition, 761-769.
- Smock, B.; Pesala, R.; and Abraham, R. 2022. PubTables-1M: Towards comprehensive table extraction from unstructured documents. In Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition, 4634-4642.
- Somvanshi, S.; Das, S.; Javed, S. A.; Antariksa, G.; and Hossain, A. 2024. A survey on deep tabular learning. arXiv preprint arXiv:2410.12034.
- Su, A.; Wang, A.; Ye, C.; Zhou, C.; Zhang, G.; Chen, G.; Zhu, G.; Wang, H.; Xu, H.; Chen, H.; et al. 2024. Tablegpt2: A large multimodal model with tabular data integration. arXiv preprint arXiv:2411.02059.
- Sui, Y.; Zhou, M.; Zhou, M.; Han, S.; and Zhang, D. 2024. Table meets llm: Can large language models understand structured table data? a benchmark and empirical study. In Proceedings of the 17th ACM International Conference on Web Search and Data Mining, 645-654.
- Wang, P.; Bai, S.; Tan, S.; Wang, S.; Fan, Z.; Bai, J.; Chen, K.; Liu, X.; Wang, J.; Ge, W.; et al. 2024. Qwen2-vl: Enhancing vision-language model's perception of the world at any resolution. arXiv preprint arXiv:2409.12191.
- xAI. 2024. Grok-1 Model Card.
- Xia, R.; Zhang, B.; Ye, H.; Yan, X.; Liu, Q.; Zhou, H.; Chen, Z.; Ye, P.; Dou, M.; Shi, B.; et al. 2024. Chartx & chartvlm: A versatile benchmark and foundation model for complicated chart reasoning. arXiv preprint arXiv:2402.12185.
- Xia, Y.; Mukherjee, S.; Xie, Z.; Wu, J.; Li, X.; Aponte, R.; Lyu, H.; Barrow, J.; Chen, H.; Dernoncourt, F.; et al. 2025. From selection to generation: A survey of llm-based active learning. In Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), 14552-14569.
- Xue, W.; Li, Q.; and Tao, D. 2019. Res2tim: Reconstruct syntactic structures from table images. In 2019 international conference on document analysis and recognition (ICDAR), 749-755. IEEE.
- Yang, F.; Hu, L.; Liu, X.; Huang, S.; and Gu, Z. 2023. A large-scale dataset for end-to-end table recognition in the wild. Scientific Data, 10(1): 110.
- Yang, K.; Ren, J.; Zhu, Y.; and Zhang, W. 2018. Active learning for wireless IoT intrusion detection. IEEE Wireless Communications, 25(6): 19-25.
- Yang, Y.; Patel, A.; Deitke, M.; Gupta, T.; Weihs, L.; Head, A.; Yatskar, M.; Callison-Burch, C.; Krishna, R.; Kembhavi, A.; and Clark, C. 2025. Scaling Text-Rich Image Understanding via Code-Guided Synthetic Multimodal Data Generation. In Che, W.; Nabende, J.; Shutova, E.; and Pilehvar, M. T., eds., Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers), 17486-17505. Vienna, Austria: Association for Computational Linguistics. ISBN 979-8-89176-251-0.
- Yoo, D.; and Kweon, I. S. 2019. Learning loss for active learning. In Proceedings of the IEEE/CVF conference on computer vision and pattern recognition, 93-102.
- Zha, L.; Zhou, J.; Li, L.; Wang, R.; Huang, Q.; Yang, S.; Yuan, J.; Su, C.; Li, X.; Su, A.; et al. 2023. Tablegpt: Towards unifying tables, nature language and commands into one gpt. arXiv preprint arXiv:2307.08674.
- Zhang, T.; Kishore, V.; Wu, F.; Weinberger, K. Q.; and Artzi, Y. 2019. Bertscore: Evaluating text generation with bert. arXiv preprint arXiv:1904.09675.
- Zheng, M.; Feng, X.; Si, Q.; She, Q.; Lin, Z.; Jiang, W.; and Wang, W. 2024. Multimodal table understanding. arXiv preprint arXiv:2406.08100.
- Zheng, X.; Burdick, D.; Popa, L.; Zhong, X.; and Wang, N. X. R. 2021. Global table extractor (gte): A framework for joint table identification and cell structure recognition using visual context. In Proceedings of the IEEE/CVF winter conference on applications of computer vision, 697-706.
- Zhong, X.; ShafieiBavani, E.; and Jimeno Yepes, A. 2020. Image-based table recognition: data, model, and evaluation. In European conference on computer vision, 564-580. Springer.
- Zhong, X.; Tang, J.; and Yepes, A. J. 2019. Publaynet: largest dataset ever for document layout analysis. In 2019 International conference on document analysis and recognition (ICDAR), 1015-1022. IEEE.
- Zhou, Y.; Cheng, M.; Mao, Q.; Liu, Q.; Xu, F.; Li, X.; and Chen, E. 2024. Enhancing Table Recognition with Vision LLMs: A Benchmark and Neighbor-Guided Toolchain Reasoner. arXiv preprint arXiv:2412.20662.
- Zhu, Y.; and Yang, K. 2019. Tripartite active learning for interactive anomaly discovery. IEEE Access, 7: 63195-63203.

## 补充实验结果

### 多行业实验

为评估不同全球行业分类标准（GICS）板块与行业中表格的语义一致性，我们对中英文表格进行了全面相关性分析。具体而言，我们计算了每个行业类别下两种语言对应表格之间的平均两两语义相关性。指标包括 Spearman 秩相关（Spear.）、Pearson 相关（Pear.）和 Kendall's Tau（Ken.），每个指标均报告为均值 ± 半个标准差，以反映统计稳定性。结果见表 6。

每个行业分别评估，每个行业包含两行：第一行对应中文表格的语义相关性，第二行对应英文表格的语义相关性。

表 6：多个全球行业分类标准（GICS）行业表格的平均语义相关性，数值为均值加减半个标准差。对于每个行业，上方结果行表示中文表格，下一行表示英文表格。

| 板块 | 行业 | 语言 | Spear. | Pear. | Ken. |
|---|---|---|---:|---:|---:|
| Energy | Energy Equipment & Services | 中文 | 0.8021 ± 0.015 | 0.7954 ± 0.007 | 0.7311 ± 0.007 |
| Energy | Energy Equipment & Services | 英文 | 0.8204 ± 0.016 | 0.8080 ± 0.015 | 0.7551 ± 0.010 |
| Energy | Oil, Gas & Consumable Fuels | 中文 | 0.8344 ± 0.021 | 0.8047 ± 0.010 | 0.7612 ± 0.005 |
| Energy | Oil, Gas & Consumable Fuels | 英文 | 0.8121 ± 0.002 | 0.7853 ± 0.013 | 0.7224 ± 0.018 |
| Materials | Chemicals | 中文 | 0.8006 ± 0.017 | 0.8105 ± 0.015 | 0.7290 ± 0.022 |
| Materials | Chemicals | 英文 | 0.8788 ± 0.027 | 0.8446 ± 0.017 | 0.8054 ± 0.020 |
| Materials | Metals & Mining | 中文 | 0.8951 ± 0.027 | 0.8848 ± 0.028 | 0.8109 ± 0.019 |
| Materials | Metals & Mining | 英文 | 0.9091 ± 0.006 | 0.9004 ± 0.005 | 0.7923 ± 0.016 |
| Health Care | Biotechnology | 中文 | 0.8516 ± 0.016 | 0.8476 ± 0.015 | 0.7577 ± 0.015 |
| Health Care | Biotechnology | 英文 | 0.8607 ± 0.016 | 0.8394 ± 0.017 | 0.7509 ± 0.004 |
| Health Care | Pharmaceuticals | 中文 | 0.8585 ± 0.007 | 0.8347 ± 0.010 | 0.7544 ± 0.008 |
| Health Care | Pharmaceuticals | 英文 | 0.8433 ± 0.015 | 0.8172 ± 0.011 | 0.7712 ± 0.017 |
| Financials | Banks | 中文 | 0.8821 ± 0.018 | 0.8543 ± 0.019 | 0.7654 ± 0.009 |
| Financials | Banks | 英文 | 0.9007 ± 0.020 | 0.8687 ± 0.022 | 0.8147 ± 0.027 |
| Financials | Insurance | 中文 | 0.7963 ± 0.014 | 0.7896 ± 0.009 | 0.7089 ± 0.002 |
| Financials | Insurance | 英文 | 0.8191 ± 0.011 | 0.8000 ± 0.004 | 0.6891 ± 0.008 |
| Information Technology | Communications Equipment | 中文 | 0.8598 ± 0.016 | 0.8239 ± 0.011 | 0.7653 ± 0.016 |
| Information Technology | Communications Equipment | 英文 | 0.8437 ± 0.022 | 0.8171 ± 0.011 | 0.7096 ± 0.001 |
| Information Technology | Semiconductor Equipment | 中文 | 0.8243 ± 0.015 | 0.8145 ± 0.015 | 0.7505 ± 0.010 |
| Information Technology | Semiconductor Equipment | 英文 | 0.8457 ± 0.012 | 0.8019 ± 0.016 | 0.7174 ± 0.004 |
| Communication Services | Telecommunications | 中文 | 0.8826 ± 0.006 | 0.8224 ± 0.007 | 0.7338 ± 0.004 |
| Communication Services | Telecommunications | 英文 | 0.8897 ± 0.009 | 0.8656 ± 0.010 | 0.7560 ± 0.005 |
| Communication Services | Media | 中文 | 0.8537 ± 0.010 | 0.8348 ± 0.010 | 0.7299 ± 0.004 |
| Communication Services | Media | 英文 | 0.8751 ± 0.011 | 0.8322 ± 0.010 | 0.7402 ± 0.008 |
| Utilities | Electric Utilities | 中文 | 0.8941 ± 0.009 | 0.8781 ± 0.006 | 0.7885 ± 0.002 |
| Utilities | Electric Utilities | 英文 | 0.8656 ± 0.013 | 0.8346 ± 0.015 | 0.7750 ± 0.006 |
| Utilities | Gas Utilities | 中文 | 0.8338 ± 0.012 | 0.7953 ± 0.011 | 0.7287 ± 0.006 |
| Utilities | Gas Utilities | 英文 | 0.8052 ± 0.013 | 0.7940 ± 0.012 | 0.6800 ± 0.008 |
| Real Estate | Equity Real Estate Trusts | 中文 | 0.8208 ± 0.015 | 0.7890 ± 0.015 | 0.6868 ± 0.006 |
| Real Estate | Equity Real Estate Trusts | 英文 | 0.8236 ± 0.014 | 0.8163 ± 0.005 | 0.7233 ± 0.003 |
| Real Estate | Management and Development | 中文 | 0.8277 ± 0.021 | 0.8134 ± 0.015 | 0.7358 ± 0.015 |
| Real Estate | Management and Development | 英文 | 0.8155 ± 0.013 | 0.8052 ± 0.013 | 0.6986 ± 0.002 |

### 详细多样性分析

基于对爬取真实世界表格的观察，我们根据线条类型将表格分为 5 类，根据表头类型将表格分为 6 类。如图 8 所示，我们的系统能够生成指定类型的表格。在图 8 中，fully lined 表示每个单元格都有完整边框线；horizontally/vertically lineless 表示单元格缺少水平/垂直边框线；Lined Headers 表示只有表头单元格有边框线；Matrix/vertical/horizontal tables 表示表格分别具有双向表头、顶部表头或左侧表头。

然而，现有数据集通常无法覆盖这些类型。例如，PubTabNet 和 FinTabNet 来自科学论文，主要由垂直单表头表格组成，且通常只包含黑白水平线。TableBank 主要由完整边框的垂直单表头表格组成，这会削弱模型识别无线表格的能力。

图 8：TableNet 详细组成。

### 文档爬取关键词

我们使用 Selenium 爬取 Microsoft 搜索引擎，查询格式为：

```text
公司缩写 + 电信相关关键词 + filetype:pdf/doc
```

关键词见表 7。

表 7：关键词

| 公司缩写 |
|---|
| China Unicom |
| China Telecom |
| China Mobile |
| China Broadnet |

| 电信相关关键词 |
|---|
| 5G, optical fiber, telecommunications |
| operator, base station, backbone network |
| gigabit, data center, FTTR |
| quality of service, roaming, value-added services |
| service hall, network access, voice services |
| broadband, cloud computing, local area network |
| Internet of Things, gateway services, ring back tone |
| network security, Wi-Fi, core network |
| network coverage, access network, network optimization |
| customer relationship management, IPTV, 5G plans |
| data pricing, VoLTE, plan pricing |

### LLM HTML 生成提示词

#### 仅结构生成提示词

请生成一个 HTML 表格，该表格包含 `{no of rows}` 行和 `{no of cols}` 列，内容为 `{content}`。序列中只能使用 `<tr>`、`<td>`、`</tr>` 和 `</td>` 标签。请按以下 JSON 格式返回生成表格：

```json
{"html": "HTML table string"}
```

表格应包含跨多行或多列的单元格。以下两个矩阵分别表示行跨度和列跨度：

```text
Row span matrix: {row spans matrix}
Column span matrix: {col spans matrix}
```

#### 主题生成提示词

请给我 `{copy}` 个与 `{domain}` 领域高度相关的 `{lang}` 短语。每个短语都应尽可能详细且具体。然后按以下 JSON 格式返回生成短语：

```json
{"phrase": [phrase1, phrase2, phrase3, phrase4, phrase5]}
```

以下主题已经使用过。请不要重复这些主题，也不要生成与它们高度相似的内容：

```text
[Used topics]
```

#### HTML 表体填充提示词

下面是一个 `{domain}` 领域的 HTML 表格，主题为 `{topic}`，表格语言为 `{lang}`。待填充的 HTML 序列如下：

```text
{HTML CODE}
```

HTML 表格结构完整，表头部分（`<th>` 标签）已经包含列名，而表体部分（`<td>` 标签）为空。请在不改变原始 HTML 结构、属性或标签的前提下，根据给定主题和已有表头填充表体（`<td>` 标签）内容。确保表格中每个单元格都包含不同且有意义的内容。

生成 `{copy}` 个不同版本的已填充 HTML 表格。然后按以下 JSON 格式返回结果：

```json
{"html": [list of filled HTML tables]}
```

#### LLM 实验与少样本提示词

从图像中读取表格内容，并将其转换为 HTML 表格格式。HTML 必须以 `<html><body><table>` 开始，并以 `</table></body></html>` 结束，且整个 HTML 应在单行中输出。你的输出只能包含以 `<html><body><table>` 开始并以 `</table></body></html>` 结束的 HTML，不得包含其他内容。

示例：HTML1 HTML2 ...

#### HTML 表头填充提示词

你将扮演严格的 HTML 编辑器。你的任务是处理 `{domain}` 领域中主题为 `{topic}`、语言为 `{lang}` 的表格。待完成的 HTML 片段如下：

```text
{HTML CODE}
```

以上是表格表头的原始 HTML 段落。请在不改变原始 HTML 结构的前提下，填充每个 `<th>` 标签中缺失的列名。

重要规则：

- 不要添加、删除或调整任何标签、属性或结构。
- 只填充 `<th>` 标签内容；即使某个 `<th>` 标签具有 `colspan` 或 `rowspan` 属性，也必须为其分配适当列名，不能留空。
- 返回格式必须为指定 JSON 结构。

#### HTML 排序提示词

你是表格质量评估专家，擅长分析 HTML 表格的结构、语义和主题相关性。请根据以下输入，从多个维度评估表格质量，并给出具体评分理由。

维度（1 到 5，只能为整数）：

**结构正确性（structure rank）：** 分数必须严格为 `{score}`。该分数仅基于结构指标，单元格内容不影响此分数。表格每行逻辑列数如下：`{structure info prompt}`。

**主题相关性（topic rank）：** 仅基于表格内容与主题的相关性，忽略表达或语义。评估内容是否匹配主题 `{topic}`。确保完整覆盖标题中提到的维度，例如时间、地点、指标、技术、组织，不能多也不能少。检查表格是否反映以下实体信息：`{entities prompt}`。这些实体无论具体或泛化都必须包含。禁止无关或完全不相关内容。不得编造牵强理由。不要仅依赖关键词的字面出现；与主题语义对齐即可。

**语义一致性（semantic rank）：** HTML 中是否存在完全空白单元格？如有，建议用与表头一致的内容填充。表头和表体语义是否对齐？`{complex string2}`。表头是否清晰且详细？是否存在乱码或损坏字符？根据出现上述问题的单元格比例扣分。不要因孤立问题给出极低分数。`N/A`、`-` 或 `TBD` 不视为空。

**总体分（rank）：** 应为上述三个维度中的最低分。

输出格式必须严格为 JSON，不得包含额外文本。

```text
Topic: {topic}
Raw HTML Table Code: {html code}
```

#### 修改后的 CoSyn 提示词

你是一位具有广泛领域知识的内容创作专家。请根据以下设置为我生成内容材料：

```text
Topic: {TOPIC}
Figure Type: Table
```

请遵循以下要求：

- 生成材料应与主题紧密相关，并根据人物设定进行定制。
- 内容结构应适合生成指定图形类型，例如表格、图表等。
- 所有内容必须真实可信，并使用真实世界实体名称。严禁使用占位符，例如 xxA、xxB、[Name]、[Date] 等。
- 材料应具有多样性，并从不同角度覆盖主题，以保证信息丰富性和广度。
- 控制内容量，只提供关键信息，使其适合单页文档。
- 所有内容必须使用英文，即使人物设定为非英语使用者。
- 请以 JSON 格式输出，不要包含额外解释文本。

你是 HTML 文档编写专家。我有一个关于 `{TOPIC}` 的数据集，可用于生成 HTML 表格。数据如下（JSON 格式）：

```text
<data>
{DATA}
</data>
```

请使用 HTML 和 CSS 生成一个 HTML 表格，并遵循以下要求：

样式要求：

1. 你可以使用任何 CSS 框架、库或工具构建页面。
2. 保持创意，使网页在字体、颜色、边框、布局等方面具有区分度，同时与主题和目标图形类型一致。
3. 使用适当设计比例，例如边距、页面大小、内容密度等，以确保信息清晰展示，没有文字重叠或布局问题。
4. 所有内容必须显示在单页内；页面不要过长也不要过于稀疏。这一点非常重要。
5. 所有文本都必须位于表格内部。
6. 生成表格应包含 `rowspan` 或 `colspan` 属性。

代码要求：

1. 请将提供的数据直接硬编码到 HTML 页面中。不要使用任何后端调用。确保 HTML 语法和格式正确。
2. 在单个 HTML 文件中包含 HTML 和 CSS。不要使用外部资源文件。

输出要求：

- 请标记代码块。
- 不要输出任何额外解释文本；输出应为包裹在 `<html></html>` 中的单个 HTML 文件。

## 可复现性清单

### 作者说明

本文档列出评估可复现性的关键方面。请通过直接编辑 `.tex` 文件提供输入。对于每个适用问题，请将 "Type your response here" 替换为你的答案。

示例：如果问题为：

```text
\question{Proofs of all novel claims are included} {(yes/partial/no)}
Type your response here
```

你应改为：

```text
\question{Proofs of all novel claims are included} {(yes/partial/no)}
yes
```

请确保：

- 只替换 "Type your response here" 文本，不要改动其他内容。
- 使用该问题列出的选项之一，例如 yes、no、partial 或 NA。
- 不要修改 `\question` 命令的其他部分或本文档其他行。

你可以在主文件的 `\end{document}` 之前 `\input` 该 `.tex` 文件，也可以将其作为独立文档编译。请查看会议网站说明，以确认是否需要随论文一起或单独提交该清单。

### 1. 一般论文结构

1.1 是否包含所提出 AI 方法的概念性大纲和/或伪代码描述：yes

1.2 是否清楚区分观点、假设、推测与客观事实和结果：yes

1.3 是否为不熟悉领域的读者提供清晰标注的教学性参考，以获得复现论文所需背景：yes

### 2. 理论贡献

2.1 本文是否做出理论贡献：no

若是，请回答以下问题：

2.2 所有假设和限制是否清晰且形式化陈述：Type your response here

2.3 所有新颖主张是否形式化陈述，例如以定理形式：Type your response here

2.4 是否包含所有新颖主张的证明：Type your response here

2.5 是否为复杂和/或新颖结果给出证明草图或直觉解释：Type your response here

2.6 是否给出所用理论工具的适当引用：Type your response here

2.7 所有理论主张是否通过实验证明成立：Type your response here

2.8 是否包含用于消除或反驳主张的所有实验代码：Type your response here

### 3. 数据集使用

3.1 本文是否依赖一个或多个数据集：yes

3.2 是否说明为何在所选数据集上进行实验：yes

3.3 本文引入的所有新数据集是否包含在数据附录中：yes

3.4 本文引入的所有新数据集是否会在论文发表后公开，并采用允许研究免费使用的许可证：yes

3.5 所有来自既有文献的数据集是否附有适当引用：yes

3.6 所有来自既有文献的数据集是否公开可用：yes

3.7 对于非公开数据集，是否详细描述并说明公开替代方案为何不能科学满足需求：NA

### 4. 计算实验

4.1 本文是否包含计算实验：yes

4.2 是否说明论文开发过程中每个超参数尝试的数量和取值范围，以及选择最终参数设置的准则：no

4.3 数据预处理所需代码是否包含在附录中：yes

4.4 进行和分析实验所需全部源代码是否包含在代码附录中：yes

4.5 进行和分析实验所需全部源代码是否会在论文发表后公开，并采用允许研究免费使用的许可证：yes

4.6 实现新方法的所有源代码是否包含注释，说明实现细节并引用论文中对应步骤：yes

4.7 若算法依赖随机性，是否充分描述设置随机种子的方法以允许复现：NA

4.8 是否说明运行实验的计算基础设施，包括 GPU/CPU 型号、内存、操作系统、相关软件库和框架名称及版本：partial

4.9 是否形式化描述所用评估指标，并解释选择这些指标的动机：yes

4.10 是否说明用于计算每项报告结果的算法运行次数：yes

4.11 实验分析是否超越单一维度性能摘要，例如平均值/中位数，并包含变化、置信度或其他分布信息：yes

4.12 对性能提升或下降的显著性是否使用适当统计检验判断，例如 Wilcoxon signed-rank：yes

4.13 是否列出论文实验中每个模型/算法使用的所有最终超参数：yes
