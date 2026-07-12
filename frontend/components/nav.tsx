import Link from "next/link";

export function Nav() {
  return (
    <header className="divider-b bg-[var(--color-canvas)]">
      <nav className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-6">
        <Link
          href="/"
          className="flex items-center gap-2 text-[15px] font-medium tracking-tight"
        >
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--color-primary)]"
          />
          <span>Bhav</span>
          <span className="text-[var(--color-ink-muted)] font-normal">/ v0.1</span>
        </Link>
        <div className="flex items-center gap-8 text-[14px] text-[var(--color-ink-muted)]">
          <Link
            href="/"
            className="hover:text-[var(--color-ink)] transition-colors"
          >
            Runs
          </Link>
          <Link
            href="/new"
            className="hover:text-[var(--color-ink)] transition-colors"
          >
            New backtest
          </Link>
          <a
            href="https://github.com/rajmaurya0904/bhav/blob/main/docs/writing-strategies.md"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[var(--color-ink)] transition-colors"
          >
            Docs
          </a>
          <Link
            href="/new"
            className="rounded-md bg-[var(--color-primary)] px-3.5 py-1.5 text-[13px] font-medium text-white hover:bg-[var(--color-primary-hover)] transition-colors"
          >
            Run
          </Link>
        </div>
      </nav>
    </header>
  );
}
