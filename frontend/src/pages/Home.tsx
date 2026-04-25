import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { useNavigate } from "react-router-dom"
import { LayoutDashboard, MessageSquare, ShieldAlert, Zap } from "lucide-react"

export default function Home() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-background selection:bg-primary/30">
      {/* Hero Section */}
      <section className="relative pt-20 pb-32 overflow-hidden">
        <div className="container px-4 mx-auto relative z-10">
          <div className="text-center max-w-4xl mx-auto">
            <h1 className="text-6xl md:text-7xl font-extrabold tracking-tight mb-8 bg-gradient-to-b from-white to-slate-400 bg-clip-text text-transparent">
              L'IA au service de vos projets.
            </h1>
            <p className="text-xl text-muted-foreground mb-12 max-w-2xl mx-auto leading-relaxed">
              Boostez votre productivité avec PM Assistant. Analysez vos métriques Redmine, 
              générez des rapports intelligents et anticipez les risques en temps réel.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" className="h-12 px-8 text-md font-bold rounded-xl shadow-lg shadow-primary/20" onClick={() => navigate("/login")}>
                🚀 Accéder à l'Assistant
              </Button>
            </div>
          </div>
        </div>
        
        {/* Background glow effects */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[600px] bg-primary/10 blur-[120px] rounded-full pointer-events-none -z-10" />
      </section>

      {/* Features Grid */}
      <section className="py-24 bg-slate-950/50 border-t border-white/5">
        <div className="container px-4 mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <FeatureCard 
              icon={<Zap className="w-8 h-8 text-blue-400" />}
              title="Analyses Prédictives"
              description="Détectez automatiquement les retards et les goulots d'étranglement avant qu'ils ne deviennent critiques."
            />
            <FeatureCard 
              icon={<MessageSquare className="w-8 h-8 text-indigo-400" />}
              title="Multi-Agents IA"
              description="Des agents spécialisés travaillent ensemble pour vous fournir des synthèses précises de vos données Redmine."
            />
            <FeatureCard 
              icon={<LayoutDashboard className="w-8 h-8 text-violet-400" />}
              title="Monitoring Live"
              description="Suivez l'avancement global et la charge de vos équipes via un dashboard interactif ultra-fluide."
            />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-white/5 text-center text-sm text-slate-500">
        <p>PM Assistant Chatbot PFE — 2026. Optimisé pour Redmine.</p>
      </footer>
    </div>
  )
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) {
  return (
    <Card className="bg-white/5 border-white/10 hover:border-primary/50 transition-all duration-300 hover:-translate-y-1">
      <CardContent className="pt-8 p-6 text-center">
        <div className="mb-6 flex justify-center">{icon}</div>
        <h3 className="text-xl font-bold mb-3 text-slate-100">{title}</h3>
        <p className="text-slate-400 text-sm leading-relaxed">{description}</p>
      </CardContent>
    </Card>
  )
}
