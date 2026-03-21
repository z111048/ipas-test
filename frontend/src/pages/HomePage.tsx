import { Link } from 'react-router-dom'
import s1q from '@data/questions/subject1_questions.json'
import s2q from '@data/questions/subject2_questions.json'
import mock1 from '@data/questions/mock_exam1.json'
import mock2 from '@data/questions/mock_exam2.json'
import sample from '@data/questions/sample_exam.json'
import type { SubjectQuestions, ExamData } from '../types'
import StatBox from '../components/shared/StatBox'

const subject1 = s1q as SubjectQuestions
const subject2 = s2q as SubjectQuestions
const exam1 = mock1 as ExamData
const exam2 = mock2 as ExamData
const sampleExam = sample as ExamData

const totalPractice =
  subject1.chapters.reduce((a, c) => a + c.questions.length, 0) +
  subject2.chapters.reduce((a, c) => a + c.questions.length, 0)

const totalMock = exam1.total + exam2.total + sampleExam.total

export default function HomePage() {
  return (
    <div>
      <div className="text-2xl font-bold text-primary mb-1">歡迎使用 iPAS 備考平台</div>
      <div className="text-text-light mb-5">iPAS AI應用規劃師初級能力鑑定 — 完整備考資源</div>

      <div className="flex gap-3 flex-wrap mb-6">
        <StatBox value={2} label="考試科目" />
        <StatBox value={7} label="章節單元" />
        <StatBox value={totalPractice} label="章節練習題" />
        <StatBox value={totalMock} label="模擬考試題" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <Link to="/subject/s1" className="no-underline">
          <div className="bg-card rounded-xl shadow-sm border border-border p-5 cursor-pointer hover:border-accent hover:shadow-md transition-all">
            <h3 className="text-primary font-semibold mb-2">科目一：人工智慧基礎概論</h3>
            <p className="text-[0.88rem] text-text-light mb-3">涵蓋AI基礎概念、資料處理、機器學習及生成式AI等四大主題</p>
            <div className="flex flex-wrap gap-1">
              {['AI概念', '資料分析', '機器學習', '生成式AI'].map((t) => (
                <span key={t} className="text-[0.75rem] bg-[#eef5ff] text-accent px-2 py-0.5 rounded-full">{t}</span>
              ))}
            </div>
          </div>
        </Link>
        <Link to="/subject/s2" className="no-underline">
          <div className="bg-card rounded-xl shadow-sm border border-border p-5 cursor-pointer hover:border-accent hover:shadow-md transition-all">
            <h3 className="text-primary font-semibold mb-2">科目二：生成式AI應用與規劃</h3>
            <p className="text-[0.88rem] text-text-light mb-3">涵蓋No Code/Low Code平台、生成式AI工具及企業導入規劃等三大主題</p>
            <div className="flex flex-wrap gap-1">
              {['No/Low Code', 'AI工具', '導入規劃'].map((t) => (
                <span key={t} className="text-[0.75rem] bg-[#eef5ff] text-accent px-2 py-0.5 rounded-full">{t}</span>
              ))}
            </div>
          </div>
        </Link>
      </div>

      <div className="bg-card rounded-xl shadow-sm border border-border p-5 mb-4">
        <h2 className="text-lg font-semibold text-primary mb-3">📋 考試說明</h2>
        <div className="overflow-x-auto -webkit-overflow-scrolling-touch">
          <table className="w-full border-collapse text-[0.88rem] min-w-[360px]">
            <thead>
              <tr className="bg-[#f5f7fa]">
                <th className="p-2 text-left border-b border-border">項目</th>
                <th className="p-2 text-left border-b border-border">科目一</th>
                <th className="p-2 text-left border-b border-border">科目二</th>
              </tr>
            </thead>
            <tbody>
              {[
                ['科目名稱', '人工智慧基礎概論', '生成式AI應用與規劃'],
                ['題型', '四選一單選題', '四選一單選題'],
                ['及格標準', '60分', '60分'],
                ['考試時間', '90分鐘', '90分鐘'],
              ].map(([item, s1, s2], i, arr) => (
                <tr key={item}>
                  <td className={`p-2 ${i < arr.length - 1 ? 'border-b border-border' : ''}`}>{item}</td>
                  <td className={`p-2 ${i < arr.length - 1 ? 'border-b border-border' : ''}`}>{s1}</td>
                  <td className={`p-2 ${i < arr.length - 1 ? 'border-b border-border' : ''}`}>{s2}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-card rounded-xl shadow-sm border border-border p-5">
        <h2 className="text-lg font-semibold text-primary mb-3">🎯 備考建議</h2>
        <ol className="ml-5 space-y-1 text-[0.9rem] leading-7">
          <li>先閱讀各章節<strong>學習重點</strong>，理解核心概念</li>
          <li>完成各章<strong>章節練習題</strong>，找出薄弱環節</li>
          <li>透過<strong>模擬考試</strong>，熟悉答題節奏與時間管理</li>
          <li>針對錯誤題目，重新複習對應章節</li>
          <li>參考試題解析，理解命題方向與思路</li>
        </ol>
      </div>
    </div>
  )
}
