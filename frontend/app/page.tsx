"use client";

import React, { useState, useEffect } from "react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip as RechartsTooltip,
    ResponsiveContainer,
    Cell,
    LineChart,
    Line,
    Legend,
    ReferenceLine
} from "recharts";
import { Chart as GoogleChart } from "react-google-charts";
import { MessageSquareText, TrendingDown, Star, ChevronDown, ChevronUp, ThumbsUp, ThumbsDown, Loader2 } from "lucide-react";

// ============================================================================
// SOUS-COMPOSANTS UI
// ============================================================================

const KpiCard = ({ title, value, icon: Icon, colorClass, subtitle }: any) => (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex items-center justify-between transition-shadow hover:shadow-md">
        <div>
            <p className="text-sm font-semibold text-slate-500 mb-1 tracking-wide uppercase">{title}</p>
            <div className="flex flex-col items-start">
                <h3 className="text-4xl font-black text-slate-800 tracking-tight">{value}</h3>
                {subtitle && <span className="text-sm text-slate-400 mt-1">{subtitle}</span>}
            </div>
        </div>
        <div className={`p-4 rounded-2xl ${colorClass}`}>
            <Icon className="w-8 h-8" strokeWidth={2} />
        </div>
    </div>
);

const ThemeCard = ({ theme }: { theme: any }) => (
    <div className={`p-5 rounded-xl border flex flex-col justify-between ${theme.score > 0 ? 'bg-emerald-50/30 border-emerald-100' : 'bg-rose-50/30 border-rose-100'}`}>
        <div>
            <div className="flex justify-between items-center mb-3">
                <h4 className="font-bold text-slate-800 text-lg">{theme.name}</h4>
                <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-black ${theme.score > 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                    }`}>
                    {theme.score > 0 ? '+' : ''}{theme.score.toFixed(1)}
                </span>
            </div>
            <p className="text-slate-600 italic text-sm leading-relaxed">"{theme.verbatim}"</p>
        </div>
    </div>
);


// ============================================================================
// PAGE PRINCIPALE
// ============================================================================

export default function Dashboard() {
    const [showAllThemes, setShowAllThemes] = useState(false);

    // États de chargement et d'erreurs
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // États pour stocker les données de l'API FastAPI
    const [kpiData, setKpiData] = useState<any>(null);
    const [themesData, setThemesData] = useState<any[]>([]);
    const [timelineData, setTimelineData] = useState<any[]>([]);

    // useEffect principal effectuant les 3 fetch
    useEffect(() => {
        const fetchData = async () => {
            try {
                const [kpiRes, themesRes, timelineRes] = await Promise.all([
                    fetch("http://localhost:8000/api/kpi"),
                    fetch("http://localhost:8000/api/themes"),
                    fetch("http://localhost:8000/api/timeline")
                ]);

                if (!kpiRes.ok || !themesRes.ok || !timelineRes.ok) {
                    throw new Error("Une erreur s'est produite lors de la communication avec l'API FastAPI.");
                }

                const kpis = await kpiRes.json();
                const themes = await themesRes.json();
                const timeline = await timelineRes.json();

                setKpiData(kpis);
                setThemesData(themes);
                setTimelineData(timeline);
            } catch (err: any) {
                setError(err.message || "Erreur de connexion.");
            } finally {
                setIsLoading(false);
            }
        };

        fetchData();
    }, []);

    if (isLoading) {
        return (
            <div className="min-h-screen bg-[#f8fafc] flex flex-col items-center justify-center space-y-4">
                <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
                <h2 className="text-xl font-bold text-slate-600">Chargement des données Live...</h2>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-[#f8fafc] flex items-center justify-center">
                <div className="bg-red-50 p-6 rounded-xl border border-red-200 max-w-lg text-center">
                    <h2 className="text-red-600 font-bold text-xl mb-2">Erreur Serveur</h2>
                    <p className="text-red-500">{error}</p>
                </div>
            </div>
        );
    }

    // ==========================================================================
    // FORMATAGE LOGIQUE DES DONNÉES REÇUES POUR LES COMPOSANTS
    // ==========================================================================

    // 1. Sankey Data : On reconstruit les nœuds.
    const volumePositif = themesData.filter(t => t.score_moyen > 0).reduce((acc, t) => acc + t.volume, 0);
    const volumeNegatif = themesData.filter(t => t.score_moyen <= 0).reduce((acc, t) => acc + t.volume, 0);

    const SANKEY_DATA = [
        ["De", "Vers", "Volume"],
        ["Total Avis", "Positifs", volumePositif || 0.1], // Petite triche 0.1 pour éviter un crash lib si vide
        ["Total Avis", "Négatifs", volumeNegatif || 0.1],
    ];

    themesData.forEach(t => {
        if (t.score_moyen > 0) {
            SANKEY_DATA.push(["Positifs", t.categorie_macro, t.volume]);
        } else {
            SANKEY_DATA.push(["Négatifs", t.categorie_macro, t.volume]);
        }
    });

    // 2. BarChart Horizontal (Themes)
    // Recharts gère tout seul la liste, on mappe juste les clés
    const BAR_DATA = themesData.map(t => ({
        category: t.categorie_macro,
        score: t.score_moyen
    }));

    // 3. Tops et Flops
    // On crée un format homogène pour notre Composant <ThemeCard />
    const formattedThemes = themesData.map((t, idx) => ({
        id: idx,
        name: t.categorie_macro,
        score: t.score_moyen,
        type: t.score_moyen > 0 ? "positif" : "negatif",
        verbatim: t.exemple_representatif || "Aucun exemple brut disponible."
    }));

    const POSITIFS = formattedThemes.filter(t => t.score > 0).sort((a, b) => b.score - a.score);
    const NEGATIFS = formattedThemes.filter(t => t.score <= 0).sort((a, b) => a.score - b.score);

    const displayPositifs = showAllThemes ? POSITIFS : POSITIFS.slice(0, 3);
    const displayNegatifs = showAllThemes ? NEGATIFS : NEGATIFS.slice(0, 3);


    return (
        <div className="min-h-screen bg-[#f8fafc] p-4 md:p-8 font-sans">
            <div className="max-w-7xl mx-auto space-y-8">

                {/* En-tête de la page */}
                <div>
                    <h1 className="text-4xl font-extrabold text-slate-900 tracking-tight">Analyse des Feedbacks</h1>
                    <p className="text-slate-500 mt-2 text-lg">Dashboard connecté en temps réel via l'API FastAPI.</p>
                </div>

                {/* 1. Kpi Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <KpiCard
                        title="Volume total traité"
                        value={kpiData?.total_avis || 0}
                        icon={MessageSquareText}
                        colorClass="bg-blue-50 text-blue-600"
                    />
                    <KpiCard
                        title="Score moyen global"
                        value={kpiData?.score_moyen > 0 ? `+${kpiData?.score_moyen}` : kpiData?.score_moyen}
                        subtitle="Échelle [-5, +5]"
                        icon={Star}
                        colorClass="bg-amber-50 text-amber-500"
                    />
                    <KpiCard
                        title="Taux de frustration"
                        value={`${kpiData?.taux_frustration || 0}%`}
                        subtitle="Avis marqués négativement"
                        icon={TrendingDown}
                        colorClass="bg-rose-50 text-rose-600"
                    />
                </div>

                {/* 2. Vue Agrégée (Graphiques) */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                    {/* Sankey : Répartition par thèmes */}
                    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                        <h2 className="text-xl font-bold text-slate-800 mb-2">Flux de classification</h2>
                        <p className="text-sm text-slate-500 mb-6">Répartition de l'ensemble de la Data.</p>
                        <div className="h-[300px] w-full">
                            <GoogleChart
                                chartType="Sankey"
                                width="100%"
                                height="100%"
                                data={SANKEY_DATA}
                                options={{
                                    sankey: {
                                        node: { colors: ["#94a3b8", "#10b981", "#fb7185", "#3b82f6", "#f59e0b", "#6366f1", "#14b8a6"], label: { color: "#334155", bold: true, fontSize: 13 } },
                                        link: { colorMode: 'gradient', fillOpacity: 0.4 }
                                    }
                                }}
                            />
                        </div>
                    </div>

                    {/* BarChart : Sentiment Moyen par thème */}
                    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                        <h2 className="text-xl font-bold text-slate-800 mb-6">Sentiment moyen par thème</h2>
                        <div className="h-[300px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart layout="vertical" data={BAR_DATA} margin={{ top: 0, right: 30, left: 40, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                                    <XAxis type="number" domain={[-5, 5]} stroke="#94a3b8" tick={{ fontSize: 12 }} />
                                    <YAxis dataKey="category" type="category" stroke="#475569" fontWeight={600} tick={{ fontSize: 12 }} width={90} />
                                    <RechartsTooltip cursor={{ fill: '#f8fafc' }} contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                                    <ReferenceLine x={0} stroke="#cbd5e1" strokeWidth={2} />
                                    <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={20}>
                                        {BAR_DATA.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={entry.score > 0 ? '#10b981' : '#f43f5e'} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>

                {/* 3. Section Expandable Top Positifs & Négatifs */}
                <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
                    <div className="p-6 border-b border-slate-100 bg-white">
                        <h2 className="text-2xl font-bold text-slate-800">Les Tops et les Flops détaillés</h2>
                        <p className="text-slate-500 mt-1">Données issues directement de la base SQLite.</p>
                    </div>

                    <div className="p-6">
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

                            {/* Colonne POSITIFS */}
                            <div className="space-y-4">
                                <div className="flex items-center space-x-2 pb-2 border-b-2 border-emerald-100">
                                    <ThumbsUp className="w-5 h-5 text-emerald-500" />
                                    <h3 className="text-lg font-bold text-emerald-700">Champions (Positif)</h3>
                                </div>
                                <div className="grid gap-4">
                                    {displayPositifs.length > 0 ? displayPositifs.map(theme => <ThemeCard key={theme.id} theme={theme} />) : <p className="text-slate-400 italic">Aucun aspect positif.</p>}
                                </div>
                            </div>

                            {/* Colonne NÉGATIFS */}
                            <div className="space-y-4">
                                <div className="flex items-center space-x-2 pb-2 border-b-2 border-rose-100">
                                    <ThumbsDown className="w-5 h-5 text-rose-500" />
                                    <h3 className="text-lg font-bold text-rose-700">Points Critiques (Négatif)</h3>
                                </div>
                                <div className="grid gap-4">
                                    {displayNegatifs.length > 0 ? displayNegatifs.map(theme => <ThemeCard key={theme.id} theme={theme} />) : <p className="text-slate-400 italic">Aucun aspect négatif.</p>}
                                </div>
                            </div>
                        </div>

                        {/* 4. Bouton "Voir le reste" */}
                        {(POSITIFS.length > 3 || NEGATIFS.length > 3) && (
                            <div className="mt-8 flex justify-center">
                                <button
                                    onClick={() => setShowAllThemes(!showAllThemes)}
                                    className="flex items-center space-x-2 bg-slate-50 hover:bg-slate-100 text-slate-600 font-semibold px-6 py-3 rounded-full border border-slate-200 transition-colors"
                                >
                                    <span>{showAllThemes ? "Réduire la liste" : "Voir tous les thèmes"}</span>
                                    {showAllThemes ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* 5. Tendance Temporelle (LineChart) */}
                <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
                    <h2 className="text-xl font-bold text-slate-800 mb-6 flex items-center gap-2">
                        <TrendingDown className="w-5 h-5 text-slate-400" />
                        Évolution Temporelle Globale
                    </h2>
                    <div className="h-[300px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={timelineData} margin={{ top: 5, right: 20, left: -20, bottom: 0 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                                <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 13 }} />
                                <YAxis domain={[-5, 5]} stroke="#64748b" tick={{ fontSize: 13 }} />
                                <RechartsTooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                                <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px' }} />
                                <ReferenceLine y={0} stroke="#cbd5e1" strokeWidth={2} strokeDasharray="4 4" />
                                <Line type="monotone" name="Score Global Moyen" dataKey="score_moyen" stroke="#3b82f6" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>

            </div>
        </div>
    );
}
