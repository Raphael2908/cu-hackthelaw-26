import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-6 px-6">
      <h1 className="text-4xl font-semibold tracking-tight">Legal Drafting Copilot</h1>
      <p className="text-lg text-neutral-600">
        Turn a legal task brief into a synthesised argument — backed by a ranked, evaluated
        evidence set from the open web, the EU&apos;s CELLAR corpus, and your own documents. You
        decide how many of the top-ranked documents the evaluator scrutinises.
      </p>
      <div className="flex gap-3">
        <Link
          href="/tasks"
          className="rounded-md bg-black px-4 py-2 text-white hover:bg-neutral-800"
        >
          Open the console
        </Link>
        <Link
          href="/login"
          className="rounded-md border border-neutral-300 px-4 py-2 hover:bg-neutral-50"
        >
          Sign in
        </Link>
      </div>
    </main>
  );
}
