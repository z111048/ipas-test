import { useParams } from 'react-router-dom'
import s1q from '@data/questions/subject1_questions.json'
import s2q from '@data/questions/subject2_questions.json'
import type { SubjectQuestions } from '../types'
import ProgressBar from '../components/shared/ProgressBar'

const subject1 = s1q as SubjectQuestions
const subject2 = s2q as SubjectQuestions

interface ChapterInfo {
  id: string
  title: string
  description: string[]
  tags: string[]
}

const S1_CHAPTERS: ChapterInfo[] = [
  {
    id: 's1c1',
    title: '3.1 人工智慧概念',
    description: [
      '<strong>AI的定義與分類：</strong>分析型AI、預測型AI、生成型AI的特色與應用場景。',
      '<strong>AI治理概念：</strong>人機互動模式（Human-in/over/out-of-the-loop）、EU AI Act風險分級（不可接受/高/有限/低風險）。',
      '<strong>AI應用領域：</strong>醫療保健、金融、製造、教育、零售等行業的AI應用實例。',
    ],
    tags: ['AI分類', 'AI治理', 'EU AI Act'],
  },
  {
    id: 's1c2',
    title: '3.2 資料處理與分析概念',
    description: [
      '<strong>資料基本概念：</strong>結構化/非結構化資料、大數據5V特性（Volume/Velocity/Variety/Veracity/Value）。',
      '<strong>ETL流程：</strong>Extract（擷取）→ Transform（轉換：清理、排序、正規化）→ Load（載入）。',
      '<strong>資料隱私與安全：</strong>GDPR、個資法、異常值偵測（Z-score、IQR）。',
    ],
    tags: ['大數據5V', 'ETL', '資料清理', 'GDPR'],
  },
  {
    id: 's1c3',
    title: '3.3 機器學習概念',
    description: [
      '<strong>學習類型：</strong>監督式、非監督式、半監督式、強化學習的定義與適用場景。',
      '<strong>模型評估：</strong>過擬合/欠擬合、Bias-Variance Tradeoff、L1/L2正則化（Lasso/Ridge）。',
      '<strong>常見模型：</strong>決策樹、KNN、SVM、Naive Bayes、K-means分群、PCA降維。',
    ],
    tags: ['監督學習', '強化學習', '過擬合', '正則化'],
  },
  {
    id: 's1c4',
    title: '3.4 鑑別式AI與生成式AI概念',
    description: [
      '<strong>鑑別式AI：</strong>直接學習輸入特徵與標籤之間的邊界/關係，用於分類和回歸。',
      '<strong>生成式AI：</strong>LLM、Transformer架構、擴散模型（Diffusion Models），可生成文字/圖像/語音/影片。',
      '<strong>整合應用：</strong>RAG（檢索增強生成）、幻覺問題（Hallucination）、條件語言模型。',
    ],
    tags: ['LLM', 'Transformer', 'RAG', 'Diffusion'],
  },
]

const S2_CHAPTERS: ChapterInfo[] = [
  {
    id: 's2c1',
    title: '3.1 No Code / Low Code 概念',
    description: [
      '<strong>基本概念：</strong>No Code透過視覺化拖放介面，無需程式碼即可開發；Low Code提供部分程式彈性。',
      '<strong>AI民主化：</strong>讓非技術人員也能創建AI應用，降低技術門檻。',
      '<strong>優勢與限制：</strong>快速原型、成本低，但客製化有限、複雜邏輯難以實現。',
    ],
    tags: ['No Code', 'Low Code', 'AI民主化', '視覺化開發'],
  },
  {
    id: 's2c2',
    title: '3.2 生成式AI應用領域與工具使用',
    description: [
      '<strong>應用領域：</strong>文字生成（ChatGPT）、圖像生成（Midjourney/DALL-E/Stable Diffusion）、程式碼（GitHub Copilot）、語音（Whisper/ElevenLabs）。',
      '<strong>Prompt Engineering：</strong>Zero-shot、Few-shot、Chain-of-Thought、Role Prompting、APE、Graph Prompting。',
    ],
    tags: ['Prompt工程', 'ChatGPT', 'Midjourney', 'RAG'],
  },
  {
    id: 's2c3',
    title: '3.3 生成式AI導入評估規劃',
    description: [
      '<strong>導入評估：</strong>業務需求分析、ROI評估、可行性分析、供應商選擇。',
      '<strong>隱私保護：</strong>聯邦學習（Federated Learning）、同態加密、安全多方計算。',
      '<strong>風險管理：</strong>幻覺問題、資料偏見、資安威脅、治理框架建立。',
    ],
    tags: ['聯邦學習', 'ROI評估', '風險管理', 'AI治理'],
  },
]

export default function SubjectOverviewPage() {
  const { subjectId } = useParams<{ subjectId: string }>()
  const isS1 = subjectId === 's1'
  const chapters = isS1 ? S1_CHAPTERS : S2_CHAPTERS
  const data = isS1 ? subject1 : subject2
  const maxQ = Math.max(...data.chapters.map((c) => c.questions.length), 1)

  return (
    <div>
      <div className="text-2xl font-bold text-primary mb-1">
        {isS1 ? '科目一：人工智慧基礎概論' : '科目二：生成式AI應用與規劃'}
      </div>
      <div className="text-text-light mb-5">
        {isS1
          ? '評鑑主題：人工智慧概念 / 資料處理與分析概念 / 機器學習概念 / 鑑別式AI與生成式AI概念'
          : '評鑑主題：No Code/Low Code概念 / 生成式AI應用領域與工具使用 / 生成式AI導入評估規劃'}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {chapters.map((ch) => (
          <div key={ch.id} className="bg-card rounded-xl shadow-sm border border-border p-5">
            <h3 className="text-primary font-semibold mb-3">{ch.title}</h3>
            {ch.description.map((d, i) => (
              <p
                key={i}
                className="text-[0.88rem] text-app-text leading-relaxed mb-2"
                dangerouslySetInnerHTML={{ __html: d }}
              />
            ))}
            <div className="flex flex-wrap gap-1 mt-3">
              {ch.tags.map((t) => (
                <span key={t} className="text-[0.75rem] bg-[#eef5ff] text-accent px-2 py-0.5 rounded-full">{t}</span>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="bg-card rounded-xl shadow-sm border border-border p-5">
        <h2 className="text-lg font-semibold text-primary mb-4">📊 章節練習題數量</h2>
        <div className="space-y-3">
          {data.chapters.map((ch) => {
            const n = ch.questions.length
            return (
              <div key={ch.id}>
                <div className="flex justify-between text-[0.85rem] mb-1">
                  <span>{ch.title}</span>
                  <span className="text-accent font-semibold">{n} 題</span>
                </div>
                <ProgressBar percent={(n / maxQ) * 100} />
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
