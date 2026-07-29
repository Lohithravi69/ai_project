import type { Metadata } from 'next';
import { IBM_Plex_Mono, Space_Grotesk } from 'next/font/google';

import './globals.css';
import Link from 'next/link';

const spaceGrotesk = Space_Grotesk({ subsets: ['latin'], variable: '--font-sans' });
const ibmPlexMono = IBM_Plex_Mono({ subsets: ['latin'], weight: ['400', '500', '600'], variable: '--font-mono' });

export const metadata: Metadata = {
  title: 'AI Dev OS',
  description: 'Local repository intelligence for cloning, scanning, chat, and code understanding.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${ibmPlexMono.variable}`}>
      <body>
        <div className="min-h-screen bg-background">
          <header className="border-b p-4">
            <nav className="container mx-auto flex gap-4">
              <Link href="/">Dashboard</Link>
              <Link href="/semantic-search">Semantic Search</Link>
              <Link href="/project-health">Project Health</Link>
              <Link href="/rag-chat">RAG Chat</Link>
              <Link href="/project-graph">Project Graph</Link>
              <Link href="/memory-viewer">Memory Viewer</Link>
              <Link href="/retrieval-debugger">Retrieval Debugger</Link>
              <Link href="/agent-timeline">Agent Timeline</Link>
              <Link href="/token-context">Token Context</Link>
              <Link href="/system-health">System Health</Link>
              <Link href="/execution-planner">Execution Planner</Link>
              <Link href="/approval-center">Approval Center</Link>
              <Link href="/autonomous">Autonomous</Link>
              <Link href="/failure-analysis">Failure Analysis</Link>
              <Link href="/architecture-advisor">Architecture Advisor</Link>
              <Link href="/pattern-library">Pattern Library</Link>
              <Link href="/engineering-reports">Reports</Link>
            </nav>
          </header>
          <main className="container mx-auto p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
