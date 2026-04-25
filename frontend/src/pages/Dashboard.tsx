import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { 
  LayoutDashboard, 
  Users, 
  Clock, 
  AlertTriangle, 
  CheckCircle2, 
  TrendingUp,
  ChevronLeft,
  Calendar,
  Activity,
  FolderKanban,
  Zap
} from "lucide-react"
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from "recharts"
import api from "@/api/api"
import { useNavigate } from "react-router-dom"

export default function Dashboard() {
  const [metrics, setMetrics] = useState<any>(null)
  const [projectsCount, setProjectsCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    fetchMetrics()
    // Récupérer le nombre de projets depuis le localStorage
    const userDataStr = localStorage.getItem("pm_user")
    if (userDataStr) {
      const userData = JSON.parse(userDataStr)
      setProjectsCount(userData.authorized_projects?.length || 0)
    }
  }, [])

  const fetchMetrics = async () => {
    const pid = localStorage.getItem("pm_active_project")
    if (!pid) return
    try {
      const res = await api.get(`/projects/${pid}/metrics`)
      setMetrics(res.data)
    } catch (e) {
      console.error("Erreur metrics", e)
    } finally {
      setLoading(false)
    }
  }

  const isCEO = localStorage.getItem("pm_user") && (
    JSON.parse(localStorage.getItem("pm_user")!).roles?.some((r: string) => r.toUpperCase().includes("CEO")) || 
    JSON.parse(localStorage.getItem("pm_user")!).role?.toUpperCase().includes("CEO")
  );

  return (
    <div className="min-h-screen bg-[#0b0f1a] text-slate-100 p-6 md:p-10 font-sans relative overflow-hidden">
      {/* Background Decor */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-primary/2 rounded-full blur-[140px] -translate-y-1/2 translate-x-1/2 pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-purple-500/2 rounded-full blur-[140px] translate-y-1/2 -translate-x-1/2 pointer-events-none" />

      <div className="max-w-7xl mx-auto space-y-10 relative z-10">
        
        {/* Header avec Navigation */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5">
              <div className="p-1.5 bg-primary/20 rounded-lg text-primary shadow-lg shadow-primary/10">
                <LayoutDashboard className="w-5 h-5" strokeWidth={2.5} />
              </div>
              <span className="text-[11px] font-black text-slate-500 uppercase tracking-[0.3em]">Project Intelligence</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-black tracking-tighter text-white">
              Vision Analytique
            </h1>
            
            <div className="flex items-center gap-2 mt-4">
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border ${
                isCEO ? "bg-primary/10 border-primary/20 text-primary" : "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
              }`}>
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse" />
                <span className="text-[10px] font-black uppercase tracking-[0.2em]">{isCEO ? "Vue CEO" : "Vue Project Manager"}</span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
             <Button 
                variant="outline" 
                className="bg-white/5 border-white/10 hover:bg-primary/20 hover:text-primary hover:border-primary/30 text-slate-300 gap-2.5 h-12 px-6 rounded-2xl transition-all shadow-xl backdrop-blur-xl group"
                onClick={() => navigate("/chat")}
              >
                <ChevronLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" strokeWidth={2.5} />
                Retour au Chat
             </Button>
          </div>
        </header>

        {/* KPI Grid - Enhanced with 6 Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          <CardStats title="Projets Actifs" value={projectsCount} icon={<FolderKanban />} trend="Global" color="indigo" />
          <CardStats title="Avancement Global" value={`${metrics?.avg_progress || 0}%`} icon={<CheckCircle2 />} trend="+5%" color="emerald" />
          <CardStats title="Taux de Surcharge" value={`${metrics?.overload_rate || 0}%`} icon={<Zap />} trend="Alerte" color="orange" />
          <CardStats title="Total Heures" value={metrics?.total_hours || "0"} icon={<Clock />} trend="Période" color="blue" />
          <CardStats title="Équipe Projet" value={metrics?.members_count || "0"} icon={<Users />} trend="Membres" color="purple" />
          <CardStats title="Points Critiques" value={metrics?.delayed_tasks || "0"} icon={<AlertTriangle />} trend="Retards" color="red" />
        </div>

        {/* Main Visuals Area */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 bg-white/[0.03] backdrop-blur-xl border border-white/5 p-8 rounded-[32px] space-y-8 shadow-2xl relative group">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <h3 className="font-black text-xl text-white tracking-tight flex items-center gap-2">
                  Charge Opérationnelle
                  <Activity className="w-4 h-4 text-indigo-400" />
                </h3>
                <p className="text-xs text-slate-500 font-medium uppercase tracking-widest">Répartition par contributeur</p>
              </div>
            </div>

            <div className="h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={metrics?.workload_data || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                  <XAxis dataKey="name" stroke="#475569" fontSize={11} tickLine={false} axisLine={false} dy={10} />
                  <YAxis stroke="#475569" fontSize={11} tickLine={false} axisLine={false} dx={-10} />
                  <Tooltip 
                    cursor={{fill: 'rgba(255,255,255,0.02)'}}
                    contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "16px" }}
                  />
                  <Bar dataKey="hours" fill="url(#dashBar)" radius={[10, 10, 0, 0]} barSize={40} />
                  <defs>
                    <linearGradient id="dashBar" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity={0.9}/>
                      <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.1}/>
                    </linearGradient>
                  </defs>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white/[0.03] backdrop-blur-xl border border-white/5 p-8 rounded-[32px] space-y-8 shadow-2xl relative overflow-hidden group">
            <div className="space-y-1">
              <h3 className="font-black text-xl text-white tracking-tight flex items-center gap-2">
                Évolution
                <TrendingUp className="w-4 h-4 text-emerald-400" />
              </h3>
              <p className="text-xs text-slate-500 font-medium uppercase tracking-widest">Progression temporelle</p>
            </div>

            <div className="h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={metrics?.progress_data || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" />
                  <XAxis dataKey="date" stroke="#475569" fontSize={10} hide />
                  <YAxis stroke="#475569" fontSize={10} hide />
                  <Tooltip 
                     contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "16px" }}
                  />
                  <Area type="monotone" dataKey="percent" stroke="#10b981" strokeWidth={4} fillOpacity={1} fill="url(#dashGreen)" />
                  <defs>
                    <linearGradient id="dashGreen" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.2}/>
                      <stop offset="100%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}

function CardStats({ title, value, icon, trend, color }: any) {
  const colors: any = {
    blue: "text-blue-400 bg-blue-400/15 border-blue-400/20",
    purple: "text-purple-400 bg-purple-400/15 border-purple-400/20",
    red: "text-red-400 bg-red-400/15 border-red-400/20",
    emerald: "text-emerald-400 bg-emerald-400/15 border-emerald-400/20",
    indigo: "text-indigo-400 bg-indigo-400/15 border-indigo-400/20",
    orange: "text-orange-400 bg-orange-400/15 border-orange-400/20",
  }

  return (
    <div className="bg-white/[0.03] backdrop-blur-xl border border-white/5 p-7 rounded-[28px] space-y-6 hover:border-white/10 transition-all group relative overflow-hidden shadow-xl">
      <div className="flex items-center justify-between relative z-10">
        <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${colors[color]} border shadow-inner transition-transform group-hover:scale-110`}>
          {React.cloneElement(icon as React.ReactElement, { className: "w-6 h-6", strokeWidth: 2.5 })}
        </div>
        <div className={`text-[10px] font-black ${color === 'red' || color === 'orange' ? 'text-rose-400 bg-rose-400/10' : 'text-emerald-400 bg-emerald-400/10'} px-2.5 py-1.5 rounded-xl flex items-center gap-1 shadow-sm`}>
          <TrendingUp className="w-3 h-3" />
          {trend}
        </div>
      </div>
      <div className="relative z-10">
        <div className="text-3xl font-black text-white tracking-tighter">{value}</div>
        <div className="text-[10px] text-slate-500 font-bold uppercase tracking-[0.2em] mt-2 opacity-70">{title}</div>
      </div>
    </div>
  )
}
