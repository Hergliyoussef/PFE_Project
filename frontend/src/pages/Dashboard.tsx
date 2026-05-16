import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import {
  LayoutDashboard,
  Users,
  AlertTriangle,
  TrendingUp,
  ChevronLeft,
  Activity,
  Zap,
  Target,
  ArrowRight,
  Sparkles,
  CheckCircle2
} from "lucide-react"
import Sidebar from "@/components/layout/Sidebar"
import {
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  Legend,
  CartesianGrid
} from "recharts"
import api from "@/api/api"
import { useNavigate, useParams } from "react-router-dom"

export default function Dashboard() {
  const [activeAlerts, setActiveAlerts] = useState<any[]>([]);
  const { projectId } = useParams<{ projectId: string }>()
  const [pid, setPid] = useState(projectId || localStorage.getItem("pm_active_project"));

  // Synchroniser pid avec l'URL
  useEffect(() => {
    if (projectId) {
      setPid(projectId);
      setMetrics(null); // IMPORTANT: Effacer les anciennes données
      localStorage.setItem("pm_active_project", projectId);
      fetchMetrics(projectId);
    }
  }, [projectId]);

  // --- WebSocket pour Temps Réel ---
  useEffect(() => {
    if (!pid) return;

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/ws/dashboard/${pid}`;

    console.log("[WS] Connexion à", wsUrl);
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      const data = jsonParse(event.data);
      if (data?.type === "new_alert") {
        console.log("[WS] Nouvelle alerte !", data.alert);
        setActiveAlerts(prev => [data.alert, ...prev]);
        if (Notification.permission === "granted") {
          new Notification("Alerte Projet PM", { body: data.alert.message });
        }
      }
    };

    socket.onclose = () => console.log("[WS] Connexion fermée");

    return () => socket.close();
  }, [pid]);

  const jsonParse = (str: string) => {
    try { return JSON.parse(str); } catch { return null; }
  };

  const [metrics, setMetrics] = useState<any>(null)
  const [projectsCount, setProjectsCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    // Initial fetch
    const initialPid = projectId || localStorage.getItem("pm_active_project");
    if (initialPid) fetchMetrics(initialPid);

    // Auto-refresh data every 5 seconds for Real-time feel
    const interval = setInterval(() => {
      const currentPid = projectId || localStorage.getItem("pm_active_project");
      if (currentPid) fetchMetrics(currentPid);
    }, 5000)

    const userDataStr = localStorage.getItem("pm_user")
    if (userDataStr) {
      const userData = JSON.parse(userDataStr)
      setProjectsCount(userData.authorized_projects?.length || 0)
    }

    return () => clearInterval(interval)
  }, [projectId])

  const fetchMetrics = async (targetPid?: string) => {
    const activePid = targetPid || projectId || localStorage.getItem("pm_active_project")
    if (!activePid) return
    setLoading(true)
    try {
      const res = await api.get(`/projects/${activePid}/metrics`)
      setMetrics(res.data)
    } catch (e) {
      console.error("Erreur metrics", e)
    } finally {
      setLoading(false)
    }
  }

  const handleProjectChange = (newPid: string) => {
    navigate(`/dashboard/${newPid}`);
  }

  const isCEO = localStorage.getItem("pm_user") && (
    JSON.parse(localStorage.getItem("pm_user")!).roles?.some((r: string) => r.toUpperCase().includes("CEO")) ||
    JSON.parse(localStorage.getItem("pm_user")!).role?.toUpperCase().includes("CEO")
  );

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <Sidebar
        onSelectConv={(id) => {
          localStorage.setItem("pm_last_conv_id", id);
          navigate("/chat");
        }}
        onNewChat={() => {
          localStorage.removeItem("pm_last_conv_id");
          navigate("/chat");
        }}
        onProjectChange={handleProjectChange}
      />

      <main key={pid} className="flex-1 overflow-y-auto relative">
        {/* Loading Overlay */}
        {loading && !metrics && (
          <div className="absolute inset-0 z-[100] flex items-center justify-center bg-background/80 backdrop-blur-sm">
            <div className="flex flex-col items-center gap-4">
              <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin" />
              <div className="text-primary font-black uppercase tracking-widest animate-pulse">Chargement des données...</div>
            </div>
          </div>
        )}

        {/* Alert Notifications Overlay */}
        <div className="fixed top-24 right-8 z-[101] flex flex-col gap-4 max-w-md">
          {activeAlerts.map((alert, idx) => (
            <div
              key={idx}
              className={`p-4 rounded-2xl border shadow-2xl backdrop-blur-2xl animate-fade-in-right flex items-start gap-4 
                ${alert.level === 'critique' ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-amber-500/10 border-amber-500/20 text-amber-400'}`}
            >
              <div className={`p-2 rounded-lg ${alert.level === 'critique' ? 'bg-red-500/20' : 'bg-amber-500/20'}`}>
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div className="flex-1 space-y-1">
                <div className="text-[10px] font-black uppercase tracking-widest opacity-70">Alerte IA {alert.type}</div>
                <p className="text-xs font-bold leading-relaxed text-white">{alert.message}</p>
              </div>
              <button
                onClick={() => setActiveAlerts(prev => prev.filter((_, i) => i !== idx))}
                className="text-white/20 hover:text-white transition-colors"
              >
                <Zap className="w-4 h-4 rotate-45" />
              </button>
            </div>
          ))}
        </div>

        {/* Cinematic Background Elements */}
        <div className="absolute top-0 left-1/4 w-[800px] h-[800px] bg-primary/5 rounded-full blur-[160px] -z-10 animate-pulse duration-[10s]" />
        <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-emerald-500/5 rounded-full blur-[140px] -z-10 animate-float" />
        <div className="absolute inset-0 bg-background/50 pointer-events-none -z-5" />

        <div className="max-w-[1600px] mx-auto p-4 md:p-6 space-y-6 relative z-10">

          {/* Futuristic Header */}
          <header className="flex flex-col md:flex-row items-center justify-between gap-8 py-6 border-b border-border backdrop-blur-md sticky top-0 z-50">
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                className="h-8 w-8 p-0 hover:bg-primary/10 text-slate-400 hover:text-primary transition-all rounded-lg border border-transparent hover:border-primary/20 -ml-2"
                onClick={() => navigate("/chat")}
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>

              <div className="relative group">
                <div className="absolute inset-0 bg-primary/40 blur-2xl rounded-2xl group-hover:bg-primary/60 transition-all" />
                <div className="relative p-4 bg-primary rounded-2xl text-primary-foreground shadow-2xl animate-float">
                  <LayoutDashboard className="w-8 h-8" strokeWidth={2.5} />
                </div>
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-black text-primary uppercase tracking-[0.4em]">Analyse Avancée</span>
                  <Sparkles className="w-3 h-3 text-primary animate-pulse" />
                </div>
                <h1 className="text-4xl font-black text-foreground tracking-tighter flex items-center gap-4">
                  Tableau de Bord
                  <div className="h-8 w-[2px] bg-border rotate-[20deg] mx-2" />
                  <span className="bg-gradient-to-r from-primary to-emerald-400 bg-clip-text text-transparent">
                    {metrics?.project_name || pid || "Chargement..."}
                  </span>
                </h1>
              </div>
            </div>

            <div className="flex items-center gap-6">
              {/* Indicateur de Santé Global Dynamique */}
              <div className="hidden xl:flex items-center gap-6 p-4 bg-white/5 backdrop-blur-xl border border-white/10 rounded-[32px] hover:bg-white/[0.08] transition-all">
                <div className="relative w-16 h-16">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={[
                          { value: metrics?.completion_rate || 0 },
                          { value: 100 - (metrics?.completion_rate || 0) }
                        ]}
                        innerRadius={20}
                        outerRadius={28}
                        startAngle={90}
                        endAngle={-270}
                        dataKey="value"
                      >
                        <Cell fill={metrics?.overdue_issues > 3 ? '#f43f5e' : metrics?.completion_rate > 70 ? '#9ACD32' : '#f59e0b'} stroke="none" />
                        <Cell fill="rgba(255,255,255,0.05)" stroke="none" />
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-xs font-black text-white leading-none">{metrics?.completion_rate || 0}%</span>
                  </div>
                </div>
                <div className="pr-4">
                  <div className="text-[9px] font-black text-primary uppercase tracking-widest mb-0.5">Santé Projet</div>
                  <div className={`text-sm font-black leading-tight ${metrics?.overdue_issues > 3 ? 'text-red-500' : metrics?.completion_rate > 70 ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {metrics?.overdue_issues > 3 ? 'CRITIQUE' : metrics?.completion_rate > 70 ? 'EXCELLENTE' : 'CORRECTE'}
                  </div>
                  <div className="text-[8px] text-slate-500 font-bold uppercase tracking-tight">
                    {metrics?.overdue_issues > 0 ? `${metrics.overdue_issues} retards détectés` : "Aucun risque majeur"}
                  </div>
                </div>
              </div>

              <div className="hidden lg:flex items-center gap-8 px-8 border-x border-border">
                <div className="text-center">
                  <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Statut</div>
                  {activeAlerts.length > 0 ? (
                    <div className="flex items-center gap-2 px-3 py-1 bg-rose-500/20 text-rose-400 rounded-full text-[10px] font-black border border-rose-500/30 animate-pulse">
                      <div className="w-1.5 h-1.5 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.6)]" />
                      ALERTE LIVE
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 text-emerald-400 rounded-full text-[10px] font-black border border-emerald-500/20">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      OPÉRATIONNEL
                    </div>
                  )}
                </div>
                <div className="text-center">
                  <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Rôle</div>
                  <div className="text-foreground font-bold">{isCEO ? "Accès CEO" : "Vue Manager"}</div>
                </div>
              </div>
              <Button
                onClick={() => navigate("/chat")}
                className="bg-card text-foreground border border-border hover:bg-primary hover:text-white transition-all h-14 px-8 rounded-2xl font-black uppercase tracking-widest text-xs flex items-center gap-3 group shadow-xl"
              >
                <ChevronLeft className="w-4 h-4 group-hover:-translate-x-1 transition-all" />
                Retour Chat
              </Button>
            </div>
          </header>

          {/* Hero Section - The Big Stats */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

            {/* Main Progress Circle Card */}
            <div className="lg:col-span-4 bg-gradient-to-br from-primary/60 to-primary/30 backdrop-blur-3xl border border-primary/40 p-8 rounded-[40px] flex flex-col items-center justify-center text-center space-y-6 shadow-2xl group relative overflow-hidden text-white animate-fade-in-up">
              <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
                <Target className="w-40 h-40" />
              </div>

              <div className="relative">
                <div className="w-56 h-56 rounded-full border-8 border-border flex items-center justify-center shadow-[inset_0_0_50px_rgba(0,0,0,0.02)]">
                  <div className="text-center">
                    <div className="text-6xl font-black text-white tracking-tighter mb-1">
                      {Math.round(metrics?.avg_progress || 0)}%
                    </div>
                    <div className="text-[10px] font-black text-primary uppercase tracking-[0.2em]">Avancement</div>
                  </div>
                  {/* SVG Progress Ring */}
                  <svg className="absolute -rotate-90 w-full h-full p-2">
                    <circle
                      cx="50%" cy="50%" r="48%"
                      fill="transparent"
                      stroke="currentColor"
                      strokeWidth="8"
                      strokeDasharray="301.5"
                      strokeDashoffset={301.5 - (301.5 * (metrics?.avg_progress || 0)) / 100}
                      className="text-primary transition-all duration-1000 ease-out"
                      strokeLinecap="round"
                    />
                  </svg>
                </div>
              </div>

              <div className="space-y-2">
                <h3 className="text-2xl font-black text-white tracking-tight">Objectif Projet</h3>
                <p className="text-white/80 text-sm max-w-[200px] mx-auto font-medium leading-relaxed">
                  Avancement global calculé sur l'ensemble des tickets actifs du projet Redmine.
                </p>
              </div>

              <div className="w-full h-px bg-border" />

              <div className="grid grid-cols-2 w-full gap-4">
                <div className="p-4 bg-white/5 rounded-3xl text-center">
                  <div className="text-xl font-bold text-white">{metrics?.total_hours || 0}h</div>
                  <div className="text-[9px] font-black text-white/70 uppercase tracking-widest">Heures Loguées</div>
                </div>
                <div className="p-4 bg-white/5 rounded-3xl text-center">
                  <div className="text-xl font-bold text-white">{projectsCount}</div>
                  <div className="text-[9px] font-black text-white/70 uppercase tracking-widest">Total Projets</div>
                </div>
              </div>
            </div>

            {/* Secondary Stats Grid */}
            <div className="lg:col-span-8 grid grid-cols-1 md:grid-cols-2 gap-6">
              <CardVisualStats
                title="Membres Actifs"
                value={metrics?.members_detailed?.length || "0"}
                icon={<Users className="w-10 h-10" />}
                color="emerald"
                description="Contributeurs sur ce projet"
                sparkData={[20, 40, 35, 50, 45, 60, 55]}
                className="animate-fade-in-up [animation-delay:100ms]"
                extraContent={
                  <div className="mt-4 space-y-2 max-h-[220px] overflow-y-auto pr-2 custom-scrollbar">
                    {metrics?.members_detailed?.map((m: any, i: number) => (
                      <div key={i} className="flex items-center justify-between gap-2 p-2 bg-muted/50 rounded-xl border border-border group/member hover:bg-muted transition-all duration-300">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400 font-black text-[10px]">
                            {m.name.charAt(0)}
                          </div>
                          <span className="text-xs font-bold text-foreground truncate max-w-[100px]">{m.name}</span>
                        </div>
                        <div className="flex flex-wrap gap-1 justify-end">
                          {m.roles.map((r: string, ri: number) => (
                            <span key={ri} className="text-[8px] px-2 py-0.5 bg-slate-900/40 text-white border border-white/10 rounded-lg font-black uppercase tracking-tighter">
                              {r}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                }
              />
              <CardVisualStats
                title="Risques & Retards"
                value={metrics?.delayed_tasks || "0"}
                icon={<AlertTriangle className="w-10 h-10" />}
                color="rose"
                description="Tickets avec échéance dépassée"
                sparkData={[10, 15, 8, 20, 25, 12, 18]}
                className="animate-fade-in-up [animation-delay:200ms]"
              />
              <CardVisualStats
                title="Charge Globale"
                value={metrics?.overload_rate > 0 ? `${metrics.overload_rate}%` : (metrics?.total_issues > 0 ? "Actif" : "0%")}
                icon={<Zap className="w-10 h-10" />}
                color="yellow"
                description={metrics?.overload_rate === 0 && metrics?.total_issues > 0
                  ? "Manque de 'temps estimé' sur Redmine"
                  : "Taux de saturation des ressources"}
                sparkData={metrics?.overload_rate > 0 ? [30, 45, 60, 55, 70, 85, 80] : [5, 5, 5, 5, 5, 5, 5]}
                className="animate-fade-in-up [animation-delay:300ms]"
              />
              <CardVisualStats
                title="Progression Réelle"
                value={metrics?.completion_rate ? `${Math.round(metrics.completion_rate)}%` : "0%"}
                icon={<CheckCircle2 className="w-10 h-10" />}
                color="blue"
                description="Tickets fermés vs Total tickets"
                sparkData={metrics?.completion_rate > 0 ? [5, 10, 15, metrics.completion_rate] : [2, 2, 2]}
                className="animate-fade-in-up [animation-delay:400ms]"
              />
            </div>
          </div>

          {/* Charts Section */}
          <div className="grid grid-cols-1 gap-10">

            {/* Performance Trend */}
            <div className="bg-card backdrop-blur-2xl border border-border p-6 md:p-8 rounded-[32px] space-y-6 group relative overflow-hidden animate-fade-in-up [animation-delay:500ms]">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <h3 className="text-2xl font-black text-foreground tracking-tight flex items-center gap-3">
                    Tendance de Vélocité
                    <div className="w-8 h-8 bg-emerald-500/10 rounded-full flex items-center justify-center text-emerald-400">
                      <Activity className="w-4 h-4" />
                    </div>
                  </h3>
                  <p className="text-xs text-muted-foreground font-bold uppercase tracking-widest">Évolution du taux de complétion</p>
                </div>
              </div>

              <div className="h-[400px] w-full">
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <AreaChart data={metrics?.progress_data || []} margin={{ top: 20, right: 100, left: 20, bottom: 55 }}>
                    <defs>
                      <linearGradient id="colorTrend" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#9ACD32" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#9ACD32" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                    <XAxis
                      dataKey="date"
                      axisLine={{ stroke: 'rgba(255,255,255,0.2)', strokeWidth: 1 }}
                      tickLine={false}
                      tick={{ fill: '#FFFFFF', fontSize: 12, fontWeight: 'bold' }}
                      dy={10}
                      label={{
                        value: 'Période (JJ / MM)',
                        position: 'insideBottom',
                        offset: -20,
                        fill: 'rgba(255,255,255,0.5)',
                        fontSize: 10,
                        fontWeight: 'bold'
                      }}
                    />
                    <YAxis
                      axisLine={{ stroke: 'rgba(255,255,255,0.2)', strokeWidth: 1 }}
                      tickLine={false}
                      tick={{ fill: '#FFFFFF', fontSize: 12, fontWeight: 'bold' }}
                      tickFormatter={(value) => `${value}%`}
                      dx={-10}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#020617",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: "24px",
                        boxShadow: "0 10px 30px rgba(0,0,0,0.5)"
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="percent"
                      name="Progression"
                      stroke="#9ACD32"
                      strokeWidth={4}
                      fillOpacity={1}
                      fill="url(#colorTrend)"
                      animationDuration={2000}
                      dot={{ fill: '#9ACD32', strokeWidth: 2, r: 4, stroke: '#020617' }}
                      activeDot={{ r: 8, strokeWidth: 0 }}
                    />
                    <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: '10px', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '1px' }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Decision Support Section */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pb-6">

            {/* Column 1: Status Distribution */}
            <div className="bg-card backdrop-blur-3xl border border-border p-8 rounded-[40px] flex flex-col shadow-2xl animate-fade-in-up [animation-delay:600ms]">
              <h3 className="text-2xl font-black text-foreground mb-8 flex items-center gap-3 uppercase tracking-tighter">
                États des Demandes <Activity className="w-5 h-5 text-primary" />
              </h3>
              <div className="flex-1 min-h-[220px]">
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <PieChart>
                    <Pie
                      data={metrics?.status_distribution || []}
                      innerRadius={60}
                      outerRadius={85}
                      paddingAngle={8}
                      dataKey="value"
                    >
                      {metrics?.status_distribution?.map((entry: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: "var(--popover)", border: "1px solid var(--border)", borderRadius: "16px", fontSize: "10px", color: "var(--foreground)" }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-6">
                {metrics?.status_distribution?.slice(0, 4).map((entry: any, index: number) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/5">
                    <div className="flex items-center gap-2 overflow-hidden">
                      <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: entry.color }} />
                      <span className="text-[12px] font-black text-slate-300 truncate uppercase tracking-tight">{entry.name}</span>
                    </div>
                    <span className="text-[14px] font-black text-foreground">{entry.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Column 2: Priorities */}
            <div className="bg-card backdrop-blur-3xl border border-border p-8 rounded-[40px] flex flex-col shadow-2xl animate-fade-in-up [animation-delay:700ms]">
              <h3 className="text-2xl font-black text-foreground mb-8 flex items-center gap-3 uppercase tracking-tighter">
                Priorités <Target className="w-5 h-5 text-rose-500" />
              </h3>
              <div className="flex-1 min-h-[220px]">
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <PieChart>
                    <Pie
                      data={metrics?.priority_distribution || []}
                      innerRadius={60}
                      outerRadius={85}
                      paddingAngle={8}
                      dataKey="value"
                    >
                      {metrics?.priority_distribution?.map((entry: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: "var(--popover)", border: "1px solid var(--border)", borderRadius: "16px", fontSize: "10px", color: "var(--foreground)" }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 gap-3 mt-6">
                {metrics?.priority_distribution?.slice(0, 4).map((entry: any, index: number) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/5">
                    <div className="flex items-center gap-2 overflow-hidden">
                      <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: entry.color }} />
                      <span className="text-[12px] font-black text-slate-300 truncate uppercase tracking-tight">{entry.name}</span>
                    </div>
                    <span className="text-[14px] font-black text-foreground">{entry.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Column 3: Tracker Distribution */}
            <div className="bg-card backdrop-blur-3xl border border-border p-8 rounded-[40px] flex flex-col shadow-2xl animate-fade-in-up [animation-delay:800ms]">
              <h3 className="text-2xl font-black text-foreground mb-8 flex items-center gap-3 uppercase tracking-tighter">
                Nature des Travaux <Zap className="w-5 h-5 text-yellow-500" />
              </h3>
              <div className="flex-1 min-h-[220px]">
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <BarChart data={metrics?.tracker_distribution || []} layout="vertical" margin={{ left: 20, right: 30 }}>
                    <XAxis type="number" hide />
                    <YAxis
                      dataKey="name"
                      type="category"
                      axisLine={false}
                      tickLine={false}
                      width={100}
                      tick={{ fill: '#FFFFFF', fontSize: 13, fontWeight: '800' }}
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                      contentStyle={{
                        backgroundColor: "#020617",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: "16px",
                        color: "#fff"
                      }}
                      itemStyle={{ color: "#fff" }}
                      labelStyle={{ color: "#9ACD32", fontWeight: "bold" }}
                    />
                    <Bar dataKey="value" radius={[0, 10, 10, 0]} barSize={16}>
                      {metrics?.tracker_distribution?.map((entry: any, index: number) => (
                        <Cell key={`cell-${index}`} fill={entry.color || '#3b82f6'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* ── ANALYSE DE L'ÉQUIPE & CHARGE DÉTAILLÉE ── */}
          <section className="space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-indigo-500/20 rounded-lg text-indigo-400">
                  <Users className="w-5 h-5" />
                </div>
                <h2 className="text-2xl font-black text-foreground tracking-tight">Répartition de la Charge</h2>
              </div>
              <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest border-b border-primary pb-1">Analyse par Ressource</div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Graphique de Charge (BarChart) */}
              <div className="lg:col-span-2 bg-card border border-border p-8 rounded-[40px] h-[400px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={metrics?.team_workload || []} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                    <XAxis
                      dataKey="name"
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#FFFFFF', fontSize: 10, fontWeight: 'bold' }}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#FFFFFF', fontSize: 10, fontWeight: 'bold' }}
                    />
                    <Tooltip
                      cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                      contentStyle={{ backgroundColor: "#020617", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "16px" }}
                    />
                    <Legend verticalAlign="top" align="right" />
                    <Bar name="Tickets Totaux" dataKey="total" stackId="a" fill="#6366f1" radius={[0, 0, 0, 0]} barSize={40} />
                    <Bar name="Tickets Urgents" dataKey="urgent" stackId="a" fill="#f43f5e" radius={[10, 10, 0, 0]} barSize={40} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Rappel Visuel des Membres Surchargés */}
              <div className="lg:col-span-1 space-y-4">
                {metrics?.team_workload?.filter((u: any) => u.is_overloaded || u.urgent > 1).map((user: any, i: number) => (
                  <div key={i} className="p-6 bg-red-500/10 border border-red-500/20 rounded-3xl flex items-center justify-between group hover:bg-red-500/20 transition-all">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-2xl bg-red-500 flex items-center justify-center text-white shadow-lg shadow-red-500/40">
                        <AlertTriangle className="w-6 h-6" />
                      </div>
                      <div>
                        <div className="text-foreground font-black">{user.name}</div>
                        <div className="text-[10px] text-red-400 font-bold uppercase tracking-widest">Surcharge Critique</div>
                      </div>
                    </div>
                    <div className="text-2xl font-black text-red-500">+{user.urgent}</div>
                  </div>
                ))}
                {(!metrics?.team_workload?.some((u: any) => u.is_overloaded)) && (
                  <div className="h-full flex flex-col items-center justify-center p-8 bg-emerald-500/5 border border-emerald-500/10 border-dashed rounded-[40px] text-center space-y-4">
                    <div className="p-4 bg-emerald-500/20 rounded-full text-emerald-400">
                      <CheckCircle2 className="w-10 h-10" />
                    </div>
                    <p className="text-sm text-slate-400 font-medium">Charge d'équipe équilibrée.<br />Aucun goulot d'étranglement.</p>
                  </div>
                )}
              </div>
            </div>

            {/* ── TOP CONTRIBUTEURS (BONUS) ── */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-10">
              <div className="md:col-span-3 flex items-center gap-3 mb-2">
                <Sparkles className="w-5 h-5 text-yellow-400 animate-pulse" />
                <h2 className="text-xl font-black text-white uppercase tracking-tighter">Élite du Projet</h2>
              </div>

              {metrics?.team_workload?.slice(0, 3).map((user: any, i: number) => (
                <div key={i} className="relative group overflow-hidden p-6 bg-white/5 backdrop-blur-2xl border border-white/10 rounded-[32px] hover:-translate-y-2 transition-all duration-500">
                  {/* Badge de Rang */}
                  <div className={`absolute -top-2 -right-2 w-12 h-12 flex items-center justify-center rounded-full shadow-2xl z-10 
                      ${i === 0 ? 'bg-gradient-to-br from-yellow-300 to-yellow-600' :
                      i === 1 ? 'bg-gradient-to-br from-slate-300 to-slate-500' :
                        'bg-gradient-to-br from-orange-400 to-orange-700'}`}>
                    <span className="text-white font-black text-lg">{i + 1}</span>
                  </div>

                  <div className="flex items-center gap-4 relative z-10">
                    <div className="w-16 h-16 rounded-2xl bg-white/10 border border-white/10 flex items-center justify-center text-2xl font-black text-white shadow-inner group-hover:scale-110 transition-transform">
                      {user.name.charAt(0)}
                    </div>
                    <div>
                      <div className="text-lg font-black text-white">{user.name}</div>
                      <div className="text-[10px] text-primary font-bold uppercase tracking-widest">
                        {i === 0 ? 'Leader Performance' : i === 1 ? 'Expert Technique' : 'Soutien Actif'}
                      </div>
                    </div>
                  </div>

                  <div className="mt-6 pt-6 border-t border-white/5 flex justify-between items-end">
                    <div>
                      <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mb-1">Impact Projet</div>
                      <div className="text-2xl font-black text-white">{Math.round((user.total / (metrics.total_issues || 1)) * 100)}%</div>
                    </div>
                    <div className="flex gap-1">
                      {[1, 2, 3, 4, 5].map((s) => (
                        <div key={s} className={`w-1.5 h-6 rounded-full ${s <= (5 - i) ? 'bg-primary animate-pulse' : 'bg-white/10'}`}
                          style={{ animationDelay: `${s * 100}ms` }} />
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ── LISTE DES TÂCHES CRITIQUES ── */}

          {/* Critical Tasks Table */}
          <div className="bg-white/[0.02] backdrop-blur-2xl border border-white/5 p-6 md:p-8 rounded-[32px] space-y-6">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <h3 className="text-2xl font-black text-foreground tracking-tight flex items-center gap-3">
                  Tâches les Plus Graves
                  <div className="px-3 py-1 bg-rose-500/10 border border-rose-500/20 rounded-full">
                    <span className="text-[10px] font-black text-rose-500 uppercase tracking-widest">Alerte Critique</span>
                  </div>
                </h3>
                <p className="text-xs text-slate-500 font-bold uppercase tracking-widest">Points de blocage nécessitant une attention immédiate</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="pb-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Ticket</th>
                    <th className="pb-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Priorité</th>
                    <th className="pb-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Assigné à</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {metrics?.critical_issues_list?.map((issue: any) => (
                    <tr key={issue.id} className="group hover:bg-white/[0.02] transition-colors">
                      <td className="py-4">
                        <span className="text-sm font-bold text-foreground group-hover:text-primary">#{issue.id} - {issue.subject}</span>
                      </td>
                      <td className="py-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${issue.priority === 'Urgent' || issue.priority === 'Immédiat' ? 'bg-red-500 text-white' : 'bg-white/10 text-slate-400'}`}>
                          {issue.priority}
                        </span>
                      </td>
                      <td className="py-4 text-xs text-slate-400 font-bold">{issue.assigned}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* AI Strategy & Action Plan */}
          <section className="p-8 bg-card backdrop-blur-3xl rounded-[40px] border border-border relative overflow-hidden group shadow-2xl">
            <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-all duration-700">
              <Sparkles className="w-32 h-32 text-primary/10" />
            </div>

            <div className="relative space-y-8">
              <div className="flex items-center gap-6">
                <div className="p-4 bg-white/5 rounded-2xl border border-white/10 shadow-inner group-hover:scale-110 transition-transform duration-500">
                  <Zap className="w-8 h-8 text-yellow-400 animate-pulse" />
                </div>
                <div>
                  <h2 className="text-2xl font-black text-foreground tracking-tight uppercase italic">
                    Plan d'Action <span className="text-primary">IA Recommandé</span>
                  </h2>
                  <p className="text-slate-500 font-bold text-[10px] uppercase tracking-widest">Analyse générée en temps réel</p>
                </div>
              </div>



              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
                <div className="lg:col-span-7 h-[300px] w-full">
                  <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                    <RadarChart cx="50%" cy="50%" outerRadius="80%" data={[
                      { subject: 'Charge', A: metrics?.total_issues || 0, fullMark: 20 },
                      { subject: 'Urgence', A: (metrics?.critical_issues_list?.length || 0) * 4, fullMark: 20 },
                      { subject: 'Retard', A: (metrics?.overdue_issues || 0) * 3, fullMark: 20 },
                      { subject: 'Vélocité', A: (metrics?.velocity || 0) * 5, fullMark: 20 },
                      { subject: 'Progrès', A: (metrics?.avg_progress || 0) / 5, fullMark: 20 },
                    ]}>
                      <PolarGrid stroke="#ffffff10" />
                      <PolarAngleAxis dataKey="subject" tick={{ fill: '#FFFFFF', fontSize: 12, fontWeight: 'bold' }} />
                      <Radar
                        name="Performance"
                        dataKey="A"
                        stroke="#9ACD32"
                        fill="#9ACD32"
                        fillOpacity={0.3}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>

                <div className="lg:col-span-5 space-y-4">
                  <div className="text-[10px] font-black text-primary uppercase tracking-[0.2em] mb-4">Recommandations IA</div>

                  {[
                    {
                      text: metrics?.overdue_issues > 0 ? `Réassigner les ${metrics.overdue_issues} tâches en retard pour débloquer le flux.` : "Maintenir le rythme actuel, aucune congestion détectée.",
                      icon: <Activity className="w-4 h-4 text-emerald-400" />,
                      status: metrics?.overdue_issues > 0 ? "Priorité Haute" : "Optimisation"
                    },
                    {
                      text: metrics?.bottleneck_alert ? "Rééquilibrer la charge de travail pour éviter le burn-out d'un membre." : "La répartition de l'équipe est saine et équilibrée.",
                      icon: <Users className="w-4 h-4 text-blue-400" />,
                      status: metrics?.bottleneck_alert ? "Alerte RH" : "Sain"
                    },
                    {
                      text: metrics?.completion_rate < 50 ? "Planifier un point d'étape urgent pour accélérer la livraison." : "Le projet est sur la bonne voie pour le prochain jalon.",
                      icon: <TrendingUp className="w-4 h-4 text-purple-400" />,
                      status: metrics?.completion_rate < 50 ? "Stratégique" : "Stable"
                    }
                  ].map((insight, idx) => (
                    <div key={idx} className="p-4 bg-white/5 border border-white/5 rounded-2xl flex items-start gap-4 hover:bg-white/[0.08] transition-all group">
                      <div className="p-2 bg-white/5 rounded-lg border border-white/5 group-hover:border-primary/40 transition-colors">
                        {insight.icon}
                      </div>
                      <div className="space-y-1">
                        <div className="text-[8px] font-black uppercase tracking-widest text-slate-500">{insight.status}</div>
                        <p className="text-xs text-white font-medium leading-relaxed">{insight.text}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}

function CardVisualStats({ title, value, icon, color, description, sparkData, extraContent, className }: any) {
  const colorStyles: any = {
    primary: "from-primary/50 to-primary/20 text-white border-primary/40",
    emerald: "from-emerald-600/50 to-emerald-600/20 text-white border-emerald-500/40",
    rose: "from-rose-600/50 to-rose-600/20 text-white border-rose-500/40",
    blue: "from-blue-600/50 to-blue-600/20 text-white border-blue-500/40",
    yellow: "from-amber-500/50 to-amber-500/20 text-white border-amber-500/40",
  }

  const chartColor = color === 'primary' ? '#9ACD32' : color === 'emerald' ? '#10b981' : color === 'rose' ? '#f43f5e' : color === 'yellow' ? '#f59e0b' : '#3b82f6';

  return (
    <div className={`bg-gradient-to-br ${colorStyles[color]} backdrop-blur-2xl border p-8 rounded-[40px] space-y-6 hover:-translate-y-2 transition-all duration-500 group relative overflow-hidden shadow-2xl ${className}`}>
      <div className="absolute inset-0 opacity-[0.03] pointer-events-none">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sparkData?.map((v: any, i: any) => ({ v, i })) || []}>
            <Area type="monotone" dataKey="v" stroke={chartColor} fill={chartColor} strokeWidth={0} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-start justify-between relative z-10">
        <div className="p-4 bg-white/10 rounded-2xl border border-white/10 shadow-inner group-hover:bg-white/20 transition-all">
          {React.cloneElement(icon as React.ReactElement<any>, { className: "w-8 h-8", strokeWidth: 2.5 })}
        </div>
        <div className="flex flex-col items-end gap-1">
          <div className="flex items-center gap-1.5 px-2 py-1 bg-white/5 rounded-lg border border-white/5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[8px] font-black text-foreground uppercase tracking-tighter">Live</span>
          </div>
        </div>
      </div>

      <div className="relative z-10">
        <div className="flex items-baseline gap-2">
          <div className="text-5xl font-black text-foreground tracking-tighter mb-2">{value}</div>
          <TrendingUp className="w-5 h-5 text-white/20" />
        </div>
        <div className="space-y-1">
          <div className="text-sm font-black text-foreground uppercase tracking-widest">{title}</div>
          <div className="text-[10px] text-white/70 font-bold uppercase tracking-widest opacity-80">{description}</div>
        </div>

        {/* New: Optional extra content (e.g. member list) */}
        {extraContent && (
          <div className="relative z-20">
            {extraContent}
          </div>
        )}
      </div>

      {/* Mini Sparkline at the bottom */}
      <div className="h-10 w-full mt-4 opacity-40 group-hover:opacity-100 transition-opacity">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <AreaChart data={sparkData?.map((v: any, i: any) => ({ v, i })) || []}>
            <Area type="monotone" dataKey="v" stroke={chartColor} strokeWidth={3} fill="transparent" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
