import Link from 'next/link';

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen">
      <header className="px-8 py-6 flex items-center justify-between border-b border-gray-800 bg-gray-900/40 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center text-xl font-bold shadow-lg shadow-indigo-500/20">
            🏛️
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
              College RAG Assistant
            </h1>
            <p className="text-xs text-gray-500">Official Campus Information System</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Link
            href="/chat"
            className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm transition shadow-lg shadow-indigo-600/30"
          >
            Launch Chatbot
          </Link>
          <Link
            href="/admin"
            className="px-4 py-2 rounded-xl border border-gray-700 hover:bg-gray-800 text-gray-300 text-sm transition"
          >
            Admin Portal
          </Link>
        </div>
      </header>

      <main className="flex-1 max-w-6xl mx-auto px-6 py-20 flex flex-col items-center text-center justify-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-indigo-500/30 bg-indigo-500/10 text-indigo-400 text-xs font-semibold mb-6">
          ✨ Powered by pgvector + Grounded RAG Orchestration
        </div>
        <h2 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-white mb-6 max-w-3xl leading-tight">
          Instant, Verified Answers from Official College Documents
        </h2>
        <p className="text-lg text-gray-400 max-w-2xl mb-10 leading-relaxed">
          Ask questions about admission deadlines, course fee schedules, hostel curfews, exam regulations, and academic calendars with transparent source citations.
        </p>

        <div className="flex flex-wrap justify-center gap-4 mb-16">
          <Link
            href="/chat"
            className="px-8 py-3.5 rounded-xl bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 hover:opacity-95 text-white font-semibold shadow-xl shadow-indigo-500/25 transition"
          >
            Start Chatting Now →
          </Link>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="px-6 py-3.5 rounded-xl border border-gray-700 bg-gray-900/60 hover:bg-gray-800 text-gray-300 font-medium text-sm transition"
          >
            Explore API Documentation
          </a>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl text-left">
          <div className="p-6 rounded-2xl border border-gray-800 bg-gray-900/30 backdrop-blur">
            <div className="text-2xl mb-3">🔍</div>
            <h3 className="text-lg font-bold text-white mb-2">Zero Hallucinations</h3>
            <p className="text-sm text-gray-400">Strict grounding policies state when evidence is missing rather than inventing policies.</p>
          </div>
          <div className="p-6 rounded-2xl border border-gray-800 bg-gray-900/30 backdrop-blur">
            <div className="text-2xl mb-3">📄</div>
            <h3 className="text-lg font-bold text-white mb-2">Exact Page Citations</h3>
            <p className="text-sm text-gray-400">Every response references the document version, page number, and section snippet.</p>
          </div>
          <div className="p-6 rounded-2xl border border-gray-800 bg-gray-900/30 backdrop-blur">
            <div className="text-2xl mb-3">🛡️</div>
            <h3 className="text-lg font-bold text-white mb-2">Admin Ingestion</h3>
            <p className="text-sm text-gray-400">Upload PDF, DOCX, or TXT documents, chunk and embed them, and publish with version control.</p>
          </div>
        </div>
      </main>
    </div>
  );
}
