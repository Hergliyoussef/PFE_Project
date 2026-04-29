import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { useNavigate } from "react-router-dom"
import { LayoutDashboard, MessageSquare, Zap } from "lucide-react"

export default function Home() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-background selection:bg-primary/30">
      {/* Hero Section */}
      <section className="relative pt-16 pb-12 overflow-hidden animate-fade-in-up">
        <div className="container px-4 mx-auto relative z-10">
          <div className="text-center max-w-4xl mx-auto">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-[11px] font-bold mb-5 animate-scale-in">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
              </span>
              Solution de gestion assistée par IA
            </div>
            <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight mb-5 bg-gradient-to-b from-white to-slate-400 bg-clip-text text-transparent drop-shadow-sm">
              L'IA au service de vos projets
            </h1>
            <p className="text-[19px] text-muted-foreground mb-6 max-w-2xl mx-auto leading-relaxed animate-fade-in [animation-delay:200ms]">
              Boostez votre productivité avec PM Assistant. Analysez vos métriques Redmine,
              générez des rapports intelligents et anticipez les risques en temps réel.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center animate-fade-in [animation-delay:400ms]">
              <Button size="lg" className="h-12 px-8 text-md font-bold rounded-xl shadow-lg shadow-primary/20 hover:shadow-primary/40 hover:scale-105 transition-all duration-300" onClick={() => navigate("/login")}>
                🚀 Accéder à l'Assistant
              </Button>
            </div>
          </div>
        </div>

        {/* Background glow effects */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] bg-primary/10 blur-[120px] rounded-full pointer-events-none -z-10 animate-pulse [animation-duration:8s]" />
      </section>

      {/* Features Grid */}
      <section className="py-10 bg-slate-950/50 border-t border-white/5 animate-fade-in-up [animation-delay:600ms]">
        <div className="container px-4 mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <FeatureCard
              icon={<Zap className="w-8 h-8 text-blue-400" />}
              title="Gestion des Tâches"
              description="Créez, mettez à jour et organisez vos tickets Redmine en langage naturel avec l'assistant."
            />
            <FeatureCard
              icon={<MessageSquare className="w-8 h-8 text-indigo-400" />}
              title="Analyse de Données"
              description="Obtenez des résumés intelligents de l'état de vos projets et de la charge de vos équipes."
            />
            <FeatureCard
              icon={<LayoutDashboard className="w-8 h-8 text-violet-400" />}
              title="Planification & Suivi"
              description="Suivez l'avancement global via des graphiques interactifs et des tableaux de bord en temps réel."
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-2 border-t border-white/10 text-center text-base text-slate-500 w-fit mx-auto px-4">
        <p>PM Assistant Chatbot PFE — 2026. Optimisé pour Redmine — Hergli Youssef.</p>
      </footer>
    </div>
  )
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) {
  return (
    <Card className="glass-effect glass-effect-hover hover:-translate-y-2 hover:shadow-2xl hover:shadow-primary/10 transition-all duration-500">
      <CardContent className="pt-6 p-5 text-center">
        <div className="mb-4 flex justify-center transform group-hover:scale-110 transition-transform duration-500">{icon}</div>
        <h3 className="text-[20px] font-bold mb-2 text-slate-100">{title}</h3>
        <p className="text-slate-400 text-[15px] leading-relaxed">{description}</p>
      </CardContent>
    </Card>
  )
}
