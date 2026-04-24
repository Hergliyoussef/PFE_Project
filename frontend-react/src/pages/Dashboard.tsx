import { useState, useEffect } from "react"
import Sidebar from "@/components/layout/Sidebar"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as ChartTooltip, ResponsiveContainer,
  AreaChart, Area, PieChart, Pie, Cell
} from "recharts"
import { LayoutDashboard, CheckCircle2, AlertCircle, Clock, Loader2, BarChart3 } from "lucide-react"
import api from "@/api/api"

const COLORS = ["#6366f1", "#8b5cf6", "#d946ef", "#ec4899"]

interface ProjectMetrics {
  avancement: number
  retard: number
  risques: number
  charge: number
  total_issues: number
}

interface Project {
  id: number
  name: string
  identifier: string
}

export default function Dashboard() {
  const [activeConvId, setActiveConvId] = useState<string | undefined>()
  const [projects, setProjects] = useState<Project[]>([])
  const [metrics, setMetrics] = useState<Record<string, ProjectMetrics>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const userData = localStorage.getItem("pm_user")
    if (userData) {
      const user = JSON.parse(userData)
      const userProjects = user.authorized_projects || []
      setProjects(userProjects)
      fetchMetrics(userProjects)
    }
  }, [])

  const fetchMetrics = async (projList: Project[]) => {
    const metricsMap: Record<string, ProjectMetrics> = {}
    setLoading(true)
    
    try {
      await Promise.all(
        projList.map(async (p) => {
          try {
            const res = await api.get(`/projects/${p.identifier}/metrics`)
            metricsMap[p.identifier] = res.data
          } catch (e) {
            metricsMap[p.identifier] = { avancement: 0, retard: 0, risques: 0, charge: 0, total_issues: 0 }
          }
        })
      )
      setMetrics(metricsMap)
    } finally {
      setLoading(false)
    }
  }

  // Calculs globaux
  const totalIssues = Object.values(metrics).reduce((acc, m) => acc + (m.total_issues || 0), 0)
  const totalRetards = Object.values(metrics).reduce((acc, m) => acc + (m.retard || 0), 0)
  const totalRisques = Object.values(metrics).reduce((acc, m) => acc + (m.risques || 0), 0)
  const avgProgress = projects.length > 0 
    ? Math.round(Object.values(metrics).reduce((acc, m) => acc + (m.avancement || 0), 0) / projects.length)
    : 0

  const chartData = projects.map(p => ({
    name: p.name.substring(0, 10),
    charge: metrics[p.identifier]?.charge || 0,
    avancement: metrics[p.identifier]?.avancement || 0
  }))

  const pieData = [
    { name: "Terminé", value: projects.filter(p => metrics[p.identifier]?.avancement === 100).length },
    { name: "En Retard", value: projects.filter(p => (metrics[p.identifier]?.retard || 0) > 0).length },
    { name: "À Risque", value: projects.filter(p => (metrics[p.identifier]?.risques || 0) > 0).length },
    { name: "En Cours", value: projects.filter(p => metrics[p.identifier]?.avancement < 100 && (metrics[p.identifier]?.retard || 0) === 0).length },
  ]

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar 
        activeConvId={activeConvId} 
        onSelectConv={(id) => setActiveConvId(id)}
        onNewChat={() => setActiveConvId(undefined)}
      />

      <main className="flex-1 overflow-y-auto p-8 selection:bg-primary/30">
        <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in duration-700">
          {/* Header */}
          <div className="flex justify-between items-end border-b border-white/5 pb-8">
            <div>
              <div className="flex items-center gap-2 mb-2 text-primary font-bold uppercase tracking-widest text-[10px]">
                <BarChart3 className="w-4 h-4" />
                Statistiques en temps réel
              </div>
              <h1 className="text-5xl font-black tracking-tight text-white">Dashboard</h1>
            </div>
            {loading && <div className="flex items-center gap-2 text-slate-500 text-sm italic"><Loader2 className="animate-spin w-4 h-4" /> Synchronisation Redmine...</div>}
          </div>

          {/* KPI Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <StatCard icon={<LayoutDashboard className="text-indigo-400" />} title="Tickets Totaux" value={totalIssues.toString()} change="+12%" />
            <StatCard icon={<Clock className="text-amber-400" />} title="Retards" value={totalRetards.toString()} change="Attention" color="amber" />
            <StatCard icon={<AlertCircle className="text-rose-400" />} title="Risques" value={totalRisques.toString()} change="Critique" color="rose" />
            <StatCard icon={<CheckCircle2 className="text-emerald-400" />} title="Progression Moy." value={`${avgProgress}%`} change="Global" color="emerald" />
          </div>

          {/* Project Table */}
          <Card className="bg-slate-900 border-white/5 overflow-hidden shadow-2xl">
            <CardHeader className="bg-white/[0.02] border-b border-white/5">
              <CardTitle className="text-lg font-bold">Avancement des Projets</CardTitle>
            </CardHeader>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="text-slate-500 uppercase text-[10px] font-bold tracking-widest border-b border-white/5">
                    <th className="px-6 py-4">Projet</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Progression</th>
                    <th className="px-6 py-4 text-right">Charge</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {projects.map((p) => {
                    const m = metrics[p.identifier] || { avancement: 0, retard: 0, risques: 0, charge: 0 }
                    const isDone = m.avancement === 100
                    const isRisk = m.risques > 0
                    const isLate = m.retard > 0

                    return (
                      <tr key={p.identifier} className="hover:bg-white/[0.02] transition-colors group">
                        <td className="px-6 py-5">
                          <div className="font-bold text-slate-200">{p.name}</div>
                          <div className="text-[10px] text-slate-500 font-mono">#{p.identifier}</div>
                        </td>
                        <td className="px-6 py-5">
                          {isDone ? (
                            <span className="px-2 py-1 bg-emerald-500/10 text-emerald-400 text-[10px] font-bold rounded-md border border-emerald-500/20">TERMINE</span>
                          ) : isRisk ? (
                            <span className="px-2 py-1 bg-rose-500/10 text-rose-400 text-[10px] font-bold rounded-md border border-rose-500/20">RISQUE</span>
                          ) : isLate ? (
                            <span className="px-2 py-1 bg-amber-500/10 text-amber-400 text-[10px] font-bold rounded-md border border-amber-500/20">RETARD</span>
                          ) : (
                            <span className="px-2 py-1 bg-blue-500/10 text-blue-400 text-[10px] font-bold rounded-md border border-blue-500/20">EN COURS</span>
                          )}
                        </td>
                        <td className="px-6 py-5">
                          <div className="flex items-center gap-3">
                            <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                              <div 
                                className={`h-full transition-all duration-1000 ${isDone ? 'bg-emerald-500' : isRisk ? 'bg-rose-500' : 'bg-primary'}`} 
                                style={{ width: `${m.avancement}%` }} 
                              />
                            </div>
                            <span className="font-bold text-xs min-w-[30px]">{m.avancement}%</span>
                          </div>
                        </td>
                        <td className="px-6 py-5 text-right font-mono text-slate-400">{m.charge} pts</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <Card className="bg-slate-900 border-white/5 shadow-xl">
              <CardHeader>
                <CardTitle className="text-lg">Charge par Projet</CardTitle>
              </CardHeader>
              <CardContent className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                    <XAxis dataKey="name" stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                    <YAxis stroke="#475569" fontSize={11} tickLine={false} axisLine={false} />
                    <ChartTooltip 
                      contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "12px" }}
                    />
                    <Bar dataKey="charge" fill="#6366f1" radius={[4, 4, 0, 0]} barSize={30} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card className="bg-slate-900 border-white/5 shadow-xl">
              <CardHeader>
                <CardTitle className="text-lg">Distribution des Statuts</CardTitle>
              </CardHeader>
              <CardContent className="h-[300px] flex items-center justify-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={5} dataKey="value">
                      {pieData.map((_, i) => <Cell key={`cell-${i}`} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <ChartTooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "12px" }} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-2 pr-8">
                  {pieData.map((item, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[i] }} />
                      <span className="text-[10px] font-bold text-slate-500 uppercase">{item.name}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}

function StatCard({ icon, title, value, change, color = "indigo" }: { icon: React.ReactNode, title: string, value: string, change: string, color?: string }) {
  const colorMap: Record<string, string> = {
    indigo: "group-hover:bg-indigo-500/10 group-hover:border-indigo-500/20",
    amber: "group-hover:bg-amber-500/10 group-hover:border-amber-500/20",
    rose: "group-hover:bg-rose-500/10 group-hover:border-rose-500/20",
    emerald: "group-hover:bg-emerald-500/10 group-hover:border-emerald-500/20",
  }

  return (
    <Card className={`bg-slate-900 border-white/5 shadow-lg transition-all duration-300 group hover:translate-y-[-2px] ${colorMap[color]}`}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="p-2.5 bg-white/[0.03] rounded-xl border border-white/5 transition-colors group-hover:bg-white/[0.05]">{icon}</div>
          <div className="text-[10px] font-black uppercase tracking-widest text-slate-500">{change}</div>
        </div>
        <div className="text-4xl font-black text-white mb-1 tabular-nums tracking-tighter">{value}</div>
        <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">{title}</div>
      </CardContent>
    </Card>
  )
}
