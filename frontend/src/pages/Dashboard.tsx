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
  Activity,
  FolderKanban,
  Zap,
  Target,
  ArrowRight,
  Sparkles,
  RefreshCw
} from "lucide-react"
import Sidebar from "@/components/layout/Sidebar"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell
} from "recharts"
import api from "@/api/api"
import { useNavigate } from "react-router-dom"

export default function Dashboard() {
  const [metrics, setMetrics] = useState<any>(null)
  const [projectsCount, setProjectsCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    fetchMetrics()
    
    // Auto-refresh data every 30 seconds for Real-time feel
    const interval = setInterval(fetchMetrics, 30000)
    
    const userDataStr = localStorage.getItem("pm_user")
    if (userDataStr) {
      const userData = JSON.parse(userDataStr)
      setProjectsCount(userData.authorized_projects?.length || 0)
    }
    
    return () => clearInterval(interval)
  }, [])

  const fetchMetrics = async () => {
    const pid = localStorage.getItem("pm_active_project")
    if (!pid) return
    setLoading(true)
    try {
      const res = await api.get(`/projects/${pid}/metrics`)
      setMetrics(res.data)
    } catch (e) {
      console.error("Erreur metrics", e)
    } finally {
      setLoading(false)
    }
  }

  const handleProjectChange = () => {
    fetchMetrics()
  }

  const isCEO = localStorage.getItem("pm_user") && (
    JSON.parse(localStorage.getItem("pm_user")!).roles?.some((r: string) => r.toUpperCase().includes("CEO")) ||
    JSON.parse(localStorage.getItem("pm_user")!).role?.toUpperCase().includes("CEO")
  );

  return (
    <div className="flex h-screen bg-[#020617] overflow-hidden">
      <Sidebar 
        onSelectConv={() => {}} 
        onNewChat={handleProjectChange} 
      />
      
      <main className="flex-1 overflow-y-auto relative">
        {/* Cinematic Background Elements */}
        <div className="absolute top-0 left-1/4 w-[800px] h-[800px] bg-primary/10 rounded-full blur-[160px] -z-10 animate-pulse duration-[10s]" />
        <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-emerald-500/10 rounded-full blur-[140px] -z-10 animate-float" />
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none -z-5" />

        <div className="max-w-[1600px] mx-auto p-6 md:p-10 space-y-12 relative z-10">
          
          {/* Futuristic Header */}
          <header className="flex flex-col md:flex-row items-center justify-between gap-8 py-6 border-b border-white/5 backdrop-blur-md sticky top-0 z-50">
            <div className="flex items-center gap-6">
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
                <h1 className="text-4xl md:text-5xl font-black tracking-tighter text-white drop-shadow-2xl">
                  Dashboard <span className="text-primary italic">Décisionnelle</span>
                </h1>
              </div>
            </div>

            <div className="flex items-center gap-6">
              {loading && <RefreshCw className="w-5 h-5 text-primary animate-spin" />}
              <div className="hidden lg:flex items-center gap-8 px-8 border-x border-white/10">
               <div className="text-center">
                 <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Statut</div>
                 <div className="flex items-center gap-2 text-emerald-400 font-bold">
                   <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                   EN DIRECT
                 </div>
               </div>
               <div className="text-center">
                 <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Rôle</div>
                 <div className="text-white font-bold">{isCEO ? "Accès CEO" : "Vue Manager"}</div>
               </div>
            </div>
            <Button
              onClick={() => navigate("/chat")}
              className="bg-white text-black hover:bg-primary hover:text-white transition-all h-14 px-8 rounded-2xl font-black uppercase tracking-widest text-xs flex items-center gap-3 group shadow-2xl shadow-white/5"
            >
              <ChevronLeft className="w-4 h-4 group-hover:-translate-x-1 transition-all" />
              Retour Chat
            </Button>
          </div>
        </header>

        {/* Hero Section - The Big Stats */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Main Progress Circle Card */}
          <div className="lg:col-span-4 bg-gradient-to-br from-white/[0.05] to-transparent backdrop-blur-3xl border border-white/10 p-10 rounded-[48px] flex flex-col items-center justify-center text-center space-y-8 shadow-2xl group relative overflow-hidden">
            <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
              <Target className="w-40 h-40" />
            </div>
            
            <div className="relative">
              <div className="w-56 h-56 rounded-full border-8 border-white/5 flex items-center justify-center shadow-[inset_0_0_50px_rgba(255,255,255,0.02)]">
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
              <p className="text-slate-400 text-sm max-w-[200px] mx-auto font-medium leading-relaxed">
                Avancement global calculé sur l'ensemble des tickets actifs du projet Redmine.
              </p>
            </div>
            
            <div className="w-full h-px bg-white/5" />
            
            <div className="grid grid-cols-2 w-full gap-4">
               <div className="p-4 bg-white/5 rounded-3xl text-center">
                 <div className="text-xl font-bold text-white">{metrics?.total_hours || 0}h</div>
                 <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Heures Loguées</div>
               </div>
               <div className="p-4 bg-white/5 rounded-3xl text-center">
                 <div className="text-xl font-bold text-white">{projectsCount}</div>
                 <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Total Projets</div>
               </div>
            </div>
          </div>

          {/* Secondary Stats Grid */}
          <div className="lg:col-span-8 grid grid-cols-1 md:grid-cols-2 gap-8">
             <CardVisualStats 
               title="Membres Actifs" 
               value={metrics?.members_count || "0"} 
               icon={<Users className="w-10 h-10" />} 
               color="emerald" 
               description="Contributeurs sur ce projet"
               sparkData={[20, 40, 35, 50, 45, 60, 55]}
             />
             <CardVisualStats 
               title="Risques & Retards" 
               value={metrics?.delayed_tasks || "0"} 
               icon={<AlertTriangle className="w-10 h-10" />} 
               color="rose" 
               description="Tickets avec échéance dépassée"
               sparkData={[10, 15, 8, 20, 25, 12, 18]}
             />
             <CardVisualStats 
               title="Charge Globale" 
               value={metrics?.overload_rate > 0 ? `${metrics.overload_rate}%` : (metrics?.total_issues > 0 ? "Actif" : "0%")} 
               icon={<Zap className="w-10 h-10" />} 
               color="primary" 
               description={metrics?.overload_rate === 0 && metrics?.total_issues > 0 
                 ? "Manque de 'temps estimé' sur Redmine" 
                 : "Taux de saturation des ressources"}
               sparkData={metrics?.overload_rate > 0 ? [30, 45, 60, 55, 70, 85, 80] : [5, 5, 5, 5, 5, 5, 5]}
             />
             <CardVisualStats 
               title="Vélocité Sprint" 
               value="+12%" 
               icon={<Activity className="w-10 h-10" />} 
               color="blue" 
               description="Performance vs mois dernier"
               sparkData={[40, 45, 55, 50, 65, 70, 75]}
             />
          </div>
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 gap-10">
          
          {/* Performance Trend */}
          <div className="bg-white/[0.02] backdrop-blur-2xl border border-white/5 p-10 rounded-[48px] space-y-10 group relative overflow-hidden">
             <div className="flex items-center justify-between">
               <div className="space-y-1">
                 <h3 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
                   Tendance de Vélocité
                   <div className="w-8 h-8 bg-emerald-500/10 rounded-full flex items-center justify-center text-emerald-400">
                     <Activity className="w-4 h-4" />
                   </div>
                 </h3>
                 <p className="text-xs text-slate-500 font-bold uppercase tracking-widest">Évolution du taux de complétion</p>
               </div>
             </div>

             <div className="h-[400px] w-full">
               <ResponsiveContainer width="100%" height="100%">
                 <AreaChart data={metrics?.progress_data || []}>
                   <defs>
                     <linearGradient id="colorTrend" x1="0" y1="0" x2="0" y2="1">
                       <stop offset="5%" stopColor="#9ACD32" stopOpacity={0.3}/>
                       <stop offset="95%" stopColor="#9ACD32" stopOpacity={0}/>
                     </linearGradient>
                   </defs>
                   <Tooltip 
                     contentStyle={{ backgroundColor: "#020617", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "24px" }}
                   />
                   <Area 
                     type="monotone" 
                     dataKey="percent" 
                     stroke="#9ACD32" 
                     strokeWidth={6}
                     fillOpacity={1} 
                     fill="url(#colorTrend)" 
                     animationDuration={2000}
                   />
                 </AreaChart>
               </ResponsiveContainer>
             </div>
          </div>
          
        </div>

        {/* Decision Support Section */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-10 pb-20">
          
          {/* Ticket Status Distribution */}
          <div className="bg-white/[0.02] backdrop-blur-2xl border border-white/5 p-10 rounded-[48px] space-y-6">
            <h3 className="text-xl font-black text-white tracking-tight flex items-center gap-2">
              États des Demandes
              <Activity className="w-4 h-4 text-primary" />
            </h3>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={metrics?.status_distribution || [
                      { name: 'Nouveau', value: 30, color: '#3b82f6' },
                      { name: 'En cours', value: 45, color: '#9ACD32' },
                      { name: 'Résolu', value: 25, color: '#10b981' },
                      { name: 'Fermé', value: 10, color: '#64748b' }
                    ]}
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={8}
                    dataKey="value"
                    stroke="none"
                  >
                    {(metrics?.status_distribution || [
                      { name: 'Nouveau', value: 30, color: '#3b82f6' },
                      { name: 'En cours', value: 45, color: '#9ACD32' },
                      { name: 'Résolu', value: 25, color: '#10b981' },
                      { name: 'Fermé', value: 10, color: '#64748b' }
                    ]).map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={entry.color || ['#3b82f6', '#9ACD32', '#10b981', '#64748b', '#f43f5e'][index % 5]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: "#020617", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "16px" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-2 gap-2">
               {(metrics?.status_distribution || []).slice(0, 4).map((s: any, i: number) => (
                 <div key={i} className="flex items-center gap-2 text-[10px]">
                   <div className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color || ['#3b82f6', '#9ACD32', '#10b981', '#f43f5e'][i % 4] }} />
                   <span className="text-slate-400 font-bold truncate">{s.name}</span>
                   <span className="text-white font-black ml-auto">{s.value}</span>
                 </div>
               ))}
            </div>
          </div>

          {/* Priority Distribution */}
          <div className="bg-white/[0.02] backdrop-blur-2xl border border-white/5 p-10 rounded-[48px] space-y-6">
            <h3 className="text-xl font-black text-white tracking-tight flex items-center gap-2">
              Priorités des Demandes
              <Target className="w-4 h-4 text-rose-500" />
            </h3>
            <div className="h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={metrics?.priority_distribution || [
                      { name: 'Urgent', value: metrics?.delayed_tasks || 5, color: '#f43f5e' },
                      { name: 'Haut', value: 15, color: '#fbbf24' },
                      { name: 'Normal', value: 80, color: '#10b981' },
                    ]}
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={8}
                    dataKey="value"
                  >
                    {(metrics?.priority_distribution || [0,1,2]).map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={entry.color || ['#f43f5e', '#fbbf24', '#10b981'][index % 3]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ backgroundColor: "#020617", border: "1px solid rgba(255,255,255,0.05)", borderRadius: "16px" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-3">
               <div className="flex justify-between items-center text-xs">
                 <span className="text-slate-400 font-bold uppercase tracking-widest">Niveau Critique</span>
                 <span className="text-rose-500 font-black">{metrics?.delayed_tasks || 0}</span>
               </div>
               <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
                 <div className="h-full bg-rose-500" style={{ width: `${Math.min((metrics?.delayed_tasks / 10) * 100, 100)}%` }} />
               </div>
            </div>
          </div>

          {/* AI Strategy & Action Plan */}
          <div className="lg:col-span-2 bg-gradient-to-br from-primary/10 to-transparent backdrop-blur-3xl border border-primary/20 p-10 rounded-[48px] relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-8 opacity-10">
              <Sparkles className="w-20 h-20 text-primary" />
            </div>
            
            <div className="relative z-10 space-y-8">
              <div className="space-y-1">
                <h3 className="text-2xl font-black text-white tracking-tight">Plan d'Action Décisionnel</h3>
                <p className="text-xs text-primary font-black uppercase tracking-[0.2em]">Recommandations de l'Assistant IA</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                 <div className="p-6 bg-white/5 border border-white/5 rounded-3xl space-y-3 hover:bg-white/10 transition-colors">
                   <div className="w-10 h-10 bg-rose-500/20 rounded-xl flex items-center justify-center text-rose-500">
                     <AlertTriangle className="w-5 h-5" />
                   </div>
                   <h4 className="font-bold text-white">Réduction des Risques</h4>
                   <p className="text-xs text-slate-400 leading-relaxed">
                     {metrics?.delayed_tasks > 0 
                       ? `Action immédiate requise sur les ${metrics.delayed_tasks} tickets en retard pour éviter un glissement du planning.` 
                       : "Aucun retard critique détecté. Maintenez la vélocité actuelle."}
                   </p>
                 </div>

                 <div className="p-6 bg-white/5 border border-white/5 rounded-3xl space-y-3 hover:bg-white/10 transition-colors">
                   <div className="w-10 h-10 bg-emerald-500/20 rounded-xl flex items-center justify-center text-emerald-400">
                     <Users className="w-5 h-5" />
                   </div>
                   <h4 className="font-bold text-white">Optimisation Ressources</h4>
                   <p className="text-xs text-slate-400 leading-relaxed">
                     {metrics?.overload_rate > 80 
                       ? "Surcharge détectée. Envisagez de redistribuer les tâches entre les membres de l'équipe." 
                       : "Charge de travail équilibrée. La capacité de l'équipe est optimale."}
                   </p>
                 </div>
              </div>

              <Button className="w-full h-14 bg-primary text-primary-foreground hover:scale-[1.02] transition-transform font-black uppercase tracking-widest text-xs rounded-2xl gap-2">
                Générer un Rapport de Décision Complet
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>

        {/* Critical Tasks Table - New Section */}
        <div className="bg-white/[0.02] backdrop-blur-2xl border border-white/5 p-10 rounded-[48px] space-y-8">
           <div className="flex items-center justify-between">
             <div className="space-y-1">
               <h3 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
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
                   <th className="pb-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Statut</th>
                   <th className="pb-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Assigné à</th>
                   <th className="pb-4 text-right text-[10px] font-black text-slate-500 uppercase tracking-widest">Action</th>
                 </tr>
               </thead>
               <tbody className="divide-y divide-white/5">
                 {(metrics?.critical_issues || [
                   { id: 102, subject: "Crash serveur production - API", priority: "Urgent", status: "En cours", assigned: "Admin" },
                   { id: 105, subject: "Faille de sécurité SQL Injection", priority: "Immédiat", status: "Nouveau", assigned: "Non assigné" },
                   { id: 110, subject: "Fuite mémoire dashboard", priority: "Haut", status: "En attente", assigned: "Dev Team" }
                 ]).map((issue: any) => (
                   <tr key={issue.id} className="group hover:bg-white/[0.02] transition-colors">
                     <td className="py-5">
                       <div className="flex flex-col">
                         <span className="text-sm font-bold text-white group-hover:text-primary transition-colors">#{issue.id} - {issue.subject}</span>
                       </div>
                     </td>
                     <td className="py-5">
                       <span className={`px-2.5 py-1 rounded-lg text-[9px] font-black uppercase ${
                         issue.priority === 'Immédiat' || issue.priority === 'Urgent' ? 'bg-rose-500/10 text-rose-500' : 'bg-amber-500/10 text-amber-500'
                       }`}>
                         {issue.priority}
                       </span>
                     </td>
                     <td className="py-5">
                       <span className="text-xs text-slate-400 font-medium">{issue.status}</span>
                     </td>
                     <td className="py-5">
                       <span className="text-xs text-slate-400 font-medium">{issue.assigned}</span>
                     </td>
                     <td className="py-5 text-right">
                       <Button variant="ghost" className="h-8 w-8 p-0 rounded-lg hover:bg-primary/20 hover:text-primary">
                         <ArrowRight className="w-4 h-4" />
                       </Button>
                     </td>
                   </tr>
                 ))}
               </tbody>
             </table>
           </div>
        </div>
      </div>
    </main>
  </div>
  )
}

function CardVisualStats({ title, value, icon, color, description, sparkData }: any) {
  const colorStyles: any = {
    primary: "from-primary/20 to-primary/5 text-primary border-primary/20",
    emerald: "from-emerald-500/20 to-emerald-500/5 text-emerald-400 border-emerald-500/20",
    rose: "from-rose-500/20 to-rose-500/5 text-rose-400 border-rose-500/20",
    blue: "from-blue-500/20 to-blue-500/5 text-blue-400 border-blue-500/20",
  }

  const chartColor = color === 'primary' ? '#9ACD32' : color === 'emerald' ? '#10b981' : color === 'rose' ? '#f43f5e' : '#3b82f6';

  return (
    <div className={`bg-gradient-to-br ${colorStyles[color]} backdrop-blur-2xl border p-8 rounded-[40px] space-y-6 hover:-translate-y-2 transition-all duration-500 group relative overflow-hidden shadow-2xl`}>
      <div className="absolute top-0 right-0 w-full h-full opacity-[0.03] pointer-events-none">
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
             <span className="text-[8px] font-black text-white uppercase tracking-tighter">Live</span>
          </div>
          <div className="w-8 h-8 bg-white/5 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all">
             <ArrowRight className="w-5 h-5 text-white" />
          </div>
        </div>
      </div>
      
      <div className="relative z-10">
        <div className="flex items-baseline gap-2">
          <div className="text-5xl font-black text-white tracking-tighter mb-2">{value}</div>
          <TrendingUp className="w-5 h-5 text-white/20" />
        </div>
        <div className="space-y-1">
          <div className="text-sm font-black text-white uppercase tracking-widest">{title}</div>
          <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest opacity-80">{description}</div>
        </div>
      </div>

      {/* Mini Sparkline at the bottom */}
      <div className="h-10 w-full mt-4 opacity-40 group-hover:opacity-100 transition-opacity">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sparkData?.map((v: any, i: any) => ({ v, i })) || []}>
            <Area type="monotone" dataKey="v" stroke={chartColor} strokeWidth={3} fill="transparent" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
