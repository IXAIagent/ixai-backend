const featureCards = [
  {
    title: "FCN 風險監控",
    body: "追蹤 KI / KO、Worst-of、配息觀察與風險燈號",
  },
  {
    title: "Crypto 策略追蹤",
    body: "監控 Grid / Dual Investment 部位狀態與價格區間",
  },
  {
    title: "AI Morning Brief",
    body: "每日整理市場新聞、部位變化與重要提醒",
  },
];

const systemCards = [
  {
    title: "AI Morning Brief",
    rows: ["Market pulse", "Portfolio changes", "Risk reminders"],
  },
  {
    title: "FCN Monitor",
    rows: ["Worst-of tracking", "KI distance", "KO observation"],
  },
  {
    title: "Portfolio Risk Dashboard",
    rows: ["Risk explanation", "Allocation advice", "Telegram alerts"],
  },
];

const steps = [
  "建立收益來源",
  "持續監控風險",
  "用數據輔助決策",
];

export default function Home() {
  return (
    <main className="min-h-screen bg-[#f5f7fb] text-slate-950">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/88 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 md:px-8">
          <a href="#top" className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-lg bg-ink text-lg font-black text-white">
              玄
            </span>
            <span>
              <span className="block text-sm font-black tracking-[0.24em] text-slate-500">
                IXAI AGENT
              </span>
              <span className="block text-lg font-black">一玄</span>
            </span>
          </a>
          <nav className="hidden items-center gap-7 text-sm font-bold text-slate-600 md:flex">
            <a href="#about" className="hover:text-slate-950">認識一玄</a>
            <a href="#system" className="hover:text-slate-950">系統展示</a>
            <a href="#logic" className="hover:text-slate-950">投資邏輯</a>
          </nav>
          <a
            href="#consult"
            className="rounded-md bg-ink px-4 py-2 text-sm font-black text-white transition hover:bg-slate-800"
          >
            預約諮詢
          </a>
        </div>
      </header>

      <section id="top" className="relative overflow-hidden bg-ink text-white">
        <div className="absolute inset-0 opacity-50 [background:linear-gradient(120deg,#08111f_0%,#14233a_45%,#0b3f44_100%)]" />
        <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-[#f5f7fb] to-transparent" />

        <div className="relative mx-auto grid min-h-[calc(100vh-73px)] max-w-7xl items-center gap-12 px-5 py-20 md:px-8 lg:grid-cols-[1.02fr_0.98fr]">
          <div>
            <p className="mb-5 text-sm font-black tracking-[0.34em] text-signal">
              一玄 IXAI Agent
            </p>
            <h1 className="max-w-4xl text-5xl font-black leading-[1.06] tracking-normal md:text-7xl">
              用 AI + FCN 打造更有紀律的投資監控系統
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-8 text-slate-300 md:text-xl">
              IXAI Agent 結合多資產部位追蹤、FCN 風險監控、Crypto Grid / Dual
              策略追蹤與 AI Morning Brief，協助投資人更清楚掌握市場與風險。
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <a
                href="#about"
                className="rounded-md bg-signal px-6 py-3 text-center text-sm font-black text-ink transition hover:bg-cyan-200"
              >
                了解 IXAI Agent
              </a>
              <a
                href="#consult"
                className="rounded-md border border-white/25 px-6 py-3 text-center text-sm font-black text-white transition hover:border-white/60 hover:bg-white/10"
              >
                預約諮詢
              </a>
            </div>
          </div>

          <div className="relative">
            <div className="rounded-lg border border-white/12 bg-white/9 p-4 shadow-panel backdrop-blur-xl">
              <div className="mb-4 flex items-center justify-between border-b border-white/10 pb-4">
                <div>
                  <p className="text-xs font-black tracking-[0.26em] text-signal">
                    LIVE MONITOR
                  </p>
                  <p className="mt-1 text-xl font-black">Portfolio Risk Dashboard</p>
                </div>
                <span className="rounded-md bg-red-400/15 px-3 py-1 text-xs font-black text-red-200">
                  HIGH
                </span>
              </div>

              <div className="grid gap-4 md:grid-cols-3">
                {["FCN", "Crypto", "Stock"].map((item, index) => (
                  <div key={item} className="rounded-md bg-white/8 p-4">
                    <p className="text-xs text-slate-400">{item}</p>
                    <p className="mt-2 text-2xl font-black">
                      {[42, 31, 27][index]}%
                    </p>
                    <div className="mt-4 h-2 rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-signal"
                        style={{ width: `${[70, 48, 36][index]}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 rounded-md bg-white/8 p-4">
                <div className="flex items-center justify-between">
                  <p className="font-black">AI Morning Brief</p>
                  <p className="text-xs text-slate-400">07:30</p>
                </div>
                <div className="mt-4 space-y-3">
                  {[
                    "BTC volatility moved above monitor band",
                    "Worst-of distance updated for FCN basket",
                    "Suggested allocation review generated",
                  ].map((row) => (
                    <div key={row} className="flex items-center gap-3 text-sm text-slate-300">
                      <span className="size-2 rounded-full bg-signal" />
                      {row}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="about" className="mx-auto grid max-w-7xl gap-8 px-5 py-24 md:px-8 lg:grid-cols-[0.95fr_1.05fr]">
        <div>
          <p className="text-sm font-black tracking-[0.24em] text-slate-500">ABOUT</p>
          <h2 className="mt-3 text-4xl font-black">認識一玄</h2>
          <p className="mt-6 text-lg leading-8 text-slate-600">
            一玄專注於 FCN 結構型商品、多資產配置與 AI 投資監控系統。透過實戰投資經驗與自動化工具，打造更有紀律、更可追蹤的投資管理流程。
          </p>
        </div>
        <div className="grid min-h-72 place-items-center rounded-lg border border-slate-200 bg-white p-8 shadow-panel">
          <div className="text-center">
            <div className="mx-auto grid size-16 place-items-center rounded-full bg-slate-100 text-2xl font-black text-slate-500">
              ▶
            </div>
            <p className="mt-5 text-lg font-black">自我介紹影片區｜未來可嵌入 YouTube 或 Vimeo</p>
          </div>
        </div>
      </section>

      <section className="bg-white py-24">
        <div className="mx-auto max-w-7xl px-5 md:px-8">
          <p className="text-sm font-black tracking-[0.24em] text-slate-500">SYSTEM</p>
          <h2 className="mt-3 text-4xl font-black">IXAI Agent 是什麼</h2>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {featureCards.map((card) => (
              <article key={card.title} className="rounded-lg border border-slate-200 bg-slate-50 p-6">
                <h3 className="text-xl font-black">{card.title}</h3>
                <p className="mt-4 leading-7 text-slate-600">{card.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="system" className="mx-auto max-w-7xl px-5 py-24 md:px-8">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="text-sm font-black tracking-[0.24em] text-slate-500">PRODUCT</p>
            <h2 className="mt-3 text-4xl font-black">系統展示</h2>
          </div>
          <p className="max-w-xl leading-7 text-slate-600">
            以 mock UI 呈現產品方向：每日簡報、FCN 監控與整體投資組合風險儀表板。
          </p>
        </div>
        <div className="mt-10 grid gap-5 lg:grid-cols-3">
          {systemCards.map((card, index) => (
            <article key={card.title} className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
              <div className="flex items-center justify-between border-b border-slate-100 pb-4">
                <h3 className="font-black">{card.title}</h3>
                <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-black text-slate-500">
                  0{index + 1}
                </span>
              </div>
              <div className="mt-5 space-y-3">
                {card.rows.map((row, rowIndex) => (
                  <div key={row} className="rounded-md bg-slate-50 p-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-bold">{row}</span>
                      <span className={rowIndex === 0 ? "text-red-500" : "text-emerald-600"}>
                        {rowIndex === 0 ? "Watch" : "OK"}
                      </span>
                    </div>
                    <div className="mt-3 h-2 rounded-full bg-slate-200">
                      <div
                        className="h-full rounded-full bg-ink"
                        style={{ width: `${82 - rowIndex * 18}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="logic" className="bg-ink py-24 text-white">
        <div className="mx-auto max-w-7xl px-5 md:px-8">
          <h2 className="max-w-3xl text-4xl font-black leading-tight">
            投資不是預測，而是建立可監控的系統
          </h2>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {steps.map((step, index) => (
              <div key={step} className="rounded-lg border border-white/10 bg-white/8 p-6">
                <p className="text-sm font-black text-signal">0{index + 1}</p>
                <h3 className="mt-4 text-2xl font-black">{step}</h3>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="consult" className="mx-auto max-w-5xl px-5 py-24 text-center md:px-8">
        <h2 className="text-4xl font-black leading-tight">
          想了解你的資產如何建立更清楚的監控流程？
        </h2>
        <a
          href="mailto:hello@ixai.agent?subject=預約 15 分鐘說明"
          className="mt-8 inline-flex rounded-md bg-ink px-7 py-4 text-sm font-black text-white transition hover:bg-slate-800"
        >
          預約 15 分鐘說明
        </a>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-5 py-8 text-sm leading-7 text-slate-500 md:px-8">
          本網站內容僅供市場資訊、投資教育與風險管理參考，不構成任何投資建議、招攬或收益保證。投資涉及風險，請自行評估並承擔相關風險。
        </div>
      </footer>
    </main>
  );
}
