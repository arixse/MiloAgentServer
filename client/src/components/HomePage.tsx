import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useScrollReveal } from '../hooks/useScrollReveal';
import { Button } from './ui/Button';
import {
  MessageSquare,
  Code2,
  FileText,
  Search,
  BarChart3,
  ArrowRight,
  Github,
  Globe,
  Terminal,
  FileCode,
  Bot,
  TrendingUp,
  Clock,
  Layers,
  ChevronDown,
} from 'lucide-react';

/* ------------------------------------------------------------------ */
/* Data
/* ------------------------------------------------------------------ */
const features = [
  {
    icon: MessageSquare,
    title: '智能对话',
    desc: '像和专家聊天一样，提问、追问、深入探讨，AI 理解你的每一个意图，给出精准详尽的回答。',
  },
  {
    icon: Code2,
    title: '代码运行',
    desc: '直接在对话中编写并运行 Python 代码，查看执行结果，调试算法，验证想法，所见即所得。',
  },
  {
    icon: Search,
    title: '联网搜索',
    desc: '实时搜索互联网最新信息，获取新闻、数据、论文，让回答始终基于最新的事实。',
  },
  {
    icon: FileText,
    title: '文件分析',
    desc: '上传 PDF、Word、Excel 等文档，AI 自动提取关键信息、总结要点、回答文档相关问题。',
  },
  {
    icon: BarChart3,
    title: '数据可视化',
    desc: '对话即可生成精美的图表——折线图、柱状图、饼图……让数据一目了然。',
  },
  {
    icon: Globe,
    title: '多场景适用',
    desc: '无论是数据分析、学术研究、编程学习还是日常工作，都能找到适合自己的用法。',
  },
];

const capabilities = [
  {
    icon: Terminal,
    title: '安全沙盒执行',
    desc: '每个用户拥有独立的代码执行环境，完全隔离，运行任意代码不会影响系统或其他用户。支持 Python 及主流数据科学库。',
  },
  {
    icon: FileCode,
    title: '多格式文件支持',
    desc: '支持 PDF、Word、Excel、CSV、图片、Markdown 等多种格式，上传即分析，智能提取结构化信息。',
  },
  {
    icon: Bot,
    title: '深度 Agent 协作',
    desc: '内置多个专业子 Agent——研究员负责搜索、分析师处理数据、报告员生成结论，团队协作完成复杂任务。',
  },
  {
    icon: Layers,
    title: '长期记忆能力',
    desc: 'Agent 会记住你的偏好和历史上下文，跨会话保持记忆，让每次对话都更加个性化、更懂你。',
  },
];

const useCases = [
  {
    title: '数据分析师',
    desc: '上传 CSV 数据，让 AI 帮你清洗、分析、可视化，几分钟完成原本需要一下午的工作。',
    icon: TrendingUp,
  },
  {
    title: '开发工程师',
    desc: '写完代码直接在沙盒中运行验证，遇到 Bug 让 AI 帮你排查，学习新技术栈的最佳实践。',
    icon: Terminal,
  },
  {
    title: '学术研究者',
    desc: '上传论文 PDF，AI 自动提取核心论点、研究方法，联网搜索相关文献，辅助文献综述。',
    icon: FileText,
  },
  {
    title: '日常办公',
    desc: '处理 Excel 报表、撰写文档大纲、搜索行业资讯……让 AI 处理重复劳动，专注于决策。',
    icon: Clock,
  },
];

const steps = [
  { step: '01', title: '登录', desc: '使用 GitHub 账号一键登录，无需额外注册，即刻开始使用。' },
  { step: '02', title: '提问', desc: '像聊天一样描述你的需求——分析数据、运行代码、搜索信息，想做什么说什么。' },
  { step: '03', title: '收获', desc: 'AI 开始工作，运行代码、搜索网络、生成图表，结果实时呈现，不满意就继续追问。' },
];

/* ------------------------------------------------------------------ */
/* Helpers
/* ------------------------------------------------------------------ */
function cn(...args: (string | false | undefined | null)[]) {
  return args.filter(Boolean).join(' ');
}

/* ------------------------------------------------------------------ */
/* Shared tiny components
/* ------------------------------------------------------------------ */

/** Icon container — consistent look across all sections */
function IconBox({ icon: Icon, className }: { icon: React.ElementType; className?: string }) {
  return (
    <div
      className={cn(
        'inline-flex items-center justify-center w-11 h-11 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 text-indigo-400 border border-white/5',
        className,
      )}
    >
      <Icon className="w-5 h-5" />
    </div>
  );
}

function SectionDivider() {
  return (
    <div className="flex justify-center py-4">
      <div className="w-24 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
    </div>
  );
}

/* ================================================================== */
/* Main
/* ================================================================== */
export function HomePage() {
  const { isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const oauthError = searchParams.get('error');

  const oauthErrorMessages: Record<string, string> = {
    access_denied: 'GitHub 授权已取消',
    invalid_state: '登录会话已过期，请重试',
    token_exchange_failed: 'GitHub 认证失败，请重试',
    user_fetch_failed: '获取 GitHub 用户信息失败',
    server_error: '服务器错误，请稍后重试',
  };
  const displayError = oauthError ? oauthErrorMessages[oauthError] || oauthError : '';

  const handleLogin = () => {
    window.location.href = '/api/auth/github';
  };

  const scrollToFeatures = () => {
    document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
  };

  /* ---- scroll-reveal refs ---- */
  const [heroRef, heroVisible] = useScrollReveal({ threshold: 0 });
  const [statsRef, statsVisible] = useScrollReveal({ threshold: 0.2 });
  const [featuresRef, featuresVisible] = useScrollReveal({ threshold: 0.1 });
  const [capRef, capVisible] = useScrollReveal({ threshold: 0.1 });
  const [ucRef, ucVisible] = useScrollReveal({ threshold: 0.1 });
  const [stepsRef, stepsVisible] = useScrollReveal({ threshold: 0.1 });

  return (
    <div className="min-h-screen bg-slate-950 text-white relative">
      {/* ================================================================ */}
      {/* Background                                                                */}
      {/* ================================================================ */}
      {/* Dot grid */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: `radial-gradient(circle, rgb(148 163 184 / 0.04) 1px, transparent 1px)`,
          backgroundSize: '32px 32px',
        }}
      />

      {/* Gradient orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none" aria-hidden>
        <div
          className="absolute -top-[20%] -left-[10%] w-[60vw] h-[60vw] rounded-full opacity-[0.18]"
          style={{
            background: 'radial-gradient(circle, rgb(99 102 241), transparent 70%)',
            animation: 'drift 14s ease-in-out infinite',
          }}
        />
        <div
          className="absolute top-[55%] -right-[10%] w-[50vw] h-[50vw] rounded-full opacity-[0.10]"
          style={{
            background: 'radial-gradient(circle, rgb(168 85 247), transparent 70%)',
            animation: 'drift 18s ease-in-out infinite reverse',
          }}
        />
        <div
          className="absolute -bottom-[10%] left-[30%] w-[40vw] h-[40vw] rounded-full opacity-[0.08]"
          style={{
            background: 'radial-gradient(circle, rgb(56 189 248), transparent 70%)',
            animation: 'drift 22s ease-in-out infinite',
          }}
        />
      </div>

      <style>{`
        @keyframes drift {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33%  { transform: translate(4vw, -4vw) scale(1.05); }
          66%  { transform: translate(-3vw, 3vw) scale(0.95); }
        }
      `}</style>

      {/* ================================================================ */}
      {/* Nav                                                                       */}
      {/* ================================================================ */}
      <nav className="relative z-10 flex items-center justify-between px-6 py-4 max-w-6xl mx-auto">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-white text-slate-900 flex items-center justify-center shadow-sm shadow-white/20">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <span className="font-semibold text-sm tracking-wide">Milo Agent</span>
        </div>
        <div className="flex items-center gap-3">
          {!isLoading &&
            (isAuthenticated ? (
              <Button size="sm" onClick={() => navigate('/chat')}>
                进入应用 <ArrowRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            ) : (
              <Button
                size="sm"
                variant="secondary"
                className="bg-white/10 hover:bg-white/20 border-0 text-white"
                onClick={handleLogin}
              >
                <Github className="w-4 h-4" /> 登录
              </Button>
            ))}
        </div>
      </nav>

      {/* ================================================================ */}
      {/* Hero                                                                      */}
      {/* ================================================================ */}
      <section
        ref={heroRef}
        className="relative z-10 max-w-4xl mx-auto px-6 pt-28 sm:pt-36 pb-20 text-center"
        style={{
          opacity: heroVisible ? 1 : 0,
          transform: heroVisible ? 'translateY(0)' : 'translateY(20px)',
          transition: 'all 0.8s ease-out',
        }}
      >
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight leading-[1.1]">
          一个对话界面，
          <br />
          <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-sky-400 bg-clip-text text-transparent">
            完成所有工作
          </span>
        </h1>

        <p className="mt-8 text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
          写代码、分析数据、搜索信息、处理文件——不再需要在无数工具之间切换。
          <br className="hidden sm:block" />
          用自然语言告诉 Milo Agent，剩下的交给 AI。
        </p>

        {/* CTA */}
        <div className="mt-10 flex flex-col items-center gap-3">
          {!isLoading &&
            (isAuthenticated ? (
              <Button
                size="lg"
                onClick={() => navigate('/chat')}
                className="px-8 text-base bg-white text-slate-900 hover:bg-gray-100 border-0 shadow-xl shadow-indigo-500/20"
              >
                进入应用 <ArrowRight className="w-5 h-5 ml-2" />
              </Button>
            ) : (
              <>
                <Button
                  size="lg"
                  onClick={handleLogin}
                  className="px-8 text-base bg-white text-slate-900 hover:bg-gray-100 border-0 shadow-xl shadow-indigo-500/25"
                >
                  <Github className="w-5 h-5" /> 使用 GitHub 免费开始
                </Button>
                {displayError && (
                  <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2.5">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
                      <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    <span>{displayError}</span>
                  </div>
                )}
                <p className="text-xs text-slate-600 mt-1">登录即表示同意服务条款和隐私政策</p>
              </>
            ))}
        </div>

        {/* Scroll hint */}
        <button
          onClick={scrollToFeatures}
          className="mt-20 mx-auto flex flex-col items-center gap-2 text-slate-600 hover:text-slate-400 transition-colors cursor-pointer bg-transparent border-0"
        >
          <span className="text-xs tracking-wider">探索更多</span>
          <ChevronDown className="w-4 h-4 animate-bounce" />
        </button>
      </section>

      <SectionDivider />

      {/* ================================================================ */}
      {/* Stats                                                                     */}
      {/* ================================================================ */}
      <section
        ref={statsRef}
        className="relative z-10 max-w-5xl mx-auto px-6 py-20"
        style={{
          opacity: statsVisible ? 1 : 0,
          transform: statsVisible ? 'translateY(0)' : 'translateY(16px)',
          transition: 'all 0.7s ease-out',
        }}
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-1">
          {[
            { n: '99.9%', label: '服务可用性' },
            { n: '毫秒级', label: '代码执行响应' },
            { n: '实时', label: '互联网信息检索' },
            { n: '全隔离', label: '沙盒安全执行' },
          ].map((s) => (
            <div key={s.label} className="text-center py-6 px-4">
              <div className="text-3xl font-bold bg-gradient-to-b from-white to-white/80 bg-clip-text text-transparent">
                {s.n}
              </div>
              <div className="text-sm text-slate-500 mt-1.5">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      <SectionDivider />

      {/* ================================================================ */}
      {/* Features                                                                  */}
      {/* ================================================================ */}
      <section
        id="features"
        ref={featuresRef}
        className="relative z-10 max-w-6xl mx-auto px-6 py-20"
        style={{
          opacity: featuresVisible ? 1 : 0,
          transform: featuresVisible ? 'translateY(0)' : 'translateY(20px)',
          transition: 'all 0.7s ease-out',
        }}
      >
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">你需要的，都在这里</h2>
          <p className="mt-3 text-slate-400 max-w-xl mx-auto">
            六大核心能力，覆盖从数据分析到日常办公的完整场景
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map((f, i) => {
            const [ref, visible] = useScrollReveal({ threshold: 0.1 });
            return (
              <div
                key={f.title}
                ref={ref}
                className="group bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 hover:bg-white/[0.06] hover:border-white/[0.12] transition-all duration-300"
                style={{
                  opacity: visible ? 1 : 0,
                  transform: visible ? 'translateY(0)' : 'translateY(24px)',
                  transition: `all 0.5s ease-out ${i * 0.08}s`,
                }}
              >
                <IconBox icon={f.icon} className="mb-4 group-hover:scale-110 transition-transform duration-300" />
                <h3 className="font-semibold text-base mb-2">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      <SectionDivider />

      {/* ================================================================ */}
      {/* Capabilities                                                              */}
      {/* ================================================================ */}
      <section
        ref={capRef}
        className="relative z-10 max-w-6xl mx-auto px-6 py-20"
        style={{
          opacity: capVisible ? 1 : 0,
          transform: capVisible ? 'translateY(0)' : 'translateY(20px)',
          transition: 'all 0.7s ease-out',
        }}
      >
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">不止于对话</h2>
          <p className="mt-3 text-slate-400 max-w-xl mx-auto">
            Milo Agent 拥有真实的工作能力，远不止一问一答
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {capabilities.map((c, i) => {
            const [ref, visible] = useScrollReveal({ threshold: 0.1 });
            return (
              <div
                key={c.title}
                ref={ref}
                className="flex gap-5 bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 hover:border-white/[0.12] transition-all duration-300"
                style={{
                  opacity: visible ? 1 : 0,
                  transform: visible ? 'translateY(0)' : 'translateY(20px)',
                  transition: `all 0.5s ease-out ${i * 0.1}s`,
                }}
              >
                <IconBox icon={c.icon} className="shrink-0" />
                <div>
                  <h3 className="font-semibold text-base mb-1.5">{c.title}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{c.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <SectionDivider />

      {/* ================================================================ */}
      {/* Use cases                                                                 */}
      {/* ================================================================ */}
      <section
        ref={ucRef}
        className="relative z-10 max-w-6xl mx-auto px-6 py-20"
        style={{
          opacity: ucVisible ? 1 : 0,
          transform: ucVisible ? 'translateY(0)' : 'translateY(20px)',
          transition: 'all 0.7s ease-out',
        }}
      >
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">谁在使用 Milo Agent</h2>
          <p className="mt-3 text-slate-400 max-w-xl mx-auto">
            无论你是什么角色，都能找到 AI 助力的方式
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {useCases.map((uc, i) => {
            const [ref, visible] = useScrollReveal({ threshold: 0.1 });
            return (
              <div
                key={uc.title}
                ref={ref}
                className="group relative overflow-hidden bg-white/[0.03] border border-white/[0.06] rounded-2xl p-6 hover:border-white/[0.12] transition-all duration-300"
                style={{
                  opacity: visible ? 1 : 0,
                  transform: visible ? 'translateY(0)' : 'translateY(20px)',
                  transition: `all 0.5s ease-out ${i * 0.1}s`,
                }}
              >
                {/* Subtle corner glow */}
                <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-indigo-500/[0.04] to-transparent rounded-bl-3xl pointer-events-none group-hover:from-indigo-500/[0.08] transition-colors duration-500" />
                <IconBox icon={uc.icon} className="mb-4 w-10 h-10 rounded-lg" />
                <h3 className="font-semibold text-base mb-2">{uc.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{uc.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      <SectionDivider />

      {/* ================================================================ */}
      {/* How it works                                                              */}
      {/* ================================================================ */}
      <section
        ref={stepsRef}
        className="relative z-10 max-w-4xl mx-auto px-6 py-20"
        style={{
          opacity: stepsVisible ? 1 : 0,
          transform: stepsVisible ? 'translateY(0)' : 'translateY(20px)',
          transition: 'all 0.7s ease-out',
        }}
      >
        <div className="text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight">三步开始</h2>
          <p className="mt-3 text-slate-400 max-w-xl mx-auto">
            简单到只需要一个 GitHub 账号
          </p>
        </div>

        <div className="flex flex-col md:flex-row items-start gap-6 md:gap-8">
          {steps.map((s, i) => {
            const [ref, visible] = useScrollReveal({ threshold: 0.15 });
            return (
              <div
                key={s.step}
                ref={ref}
                className="flex-1 flex flex-col items-center text-center relative"
                style={{
                  opacity: visible ? 1 : 0,
                  transform: visible ? 'translateY(0)' : 'translateY(20px)',
                  transition: `all 0.5s ease-out ${i * 0.15}s`,
                }}
              >
                {/* Connector line — aligns to icon centre, spans to next icon */}
                {i < steps.length - 1 && (
                  <div className="hidden md:block absolute top-8 left-[calc(50%+2rem)] w-[calc(100%-4rem)] h-px">
                    <div className="w-full h-full bg-gradient-to-r from-white/15 via-white/10 to-white/5" />
                  </div>
                )}
                <div className="relative z-10 inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 text-white font-bold text-lg mb-5 border border-white/10">
                  {s.step}
                </div>
                <h3 className="font-semibold text-base mb-2">{s.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed max-w-[240px]">{s.desc}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* ================================================================ */}
      {/* Footer                                                                    */}
      {/* ================================================================ */}
      <footer className="relative z-10 border-t border-white/[0.06] py-10 text-center">
        <div className="flex items-center justify-center gap-2 text-xs text-slate-600 mb-1.5">
          <div className="w-4 h-4 rounded bg-white/10 flex items-center justify-center">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          Milo Agent
        </div>
        <p className="text-xs text-slate-600">
          &copy; {new Date().getFullYear()} Milo Agent. All rights reserved.
        </p>
      </footer>
    </div>
  );
}
