import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { ReportResponse } from '../../types'

interface MemorialCardProps {
  report: ReportResponse
}

export function MemorialCard({ report }: MemorialCardProps) {
  const renderMarkdown = (content: string): string => {
    const rawHtml = marked.parse(content) as string
    return DOMPurify.sanitize(rawHtml)
  }

  const agentNames: Record<string, string> = {
    minister_of_revenue: 'Minister of Revenue',
    minister_of_war: 'Minister of War',
    minister_of_personnel: 'Minister of Personnel',
    minister_of_rites: 'Minister of Rites',
    minister_of_justice: 'Minister of Justice',
    minister_of_works: 'Minister of Works',
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900">
          {agentNames[report.agent_id] || report.agent_id}
        </h3>
        <span className="text-sm text-gray-500">Turn {report.turn}</span>
      </div>
      <div
        className="prose prose-sm max-w-none text-gray-700"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(report.markdown) }}
      />
    </div>
  )
}
