"use client";

import React, { useEffect, useState } from "react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from "recharts";

// Interfaces correspondant aux données renvoyées par notre API FastAPI
interface StatsData {
    total_feedbacks: number;
    score_moyen: number;
}

interface FlawData {
    categorie_macro: string;
    score_moyen: number;
    volume: number;
}

export default function DashboardPage() {
    const [stats, setStats] = useState<StatsData | null>(null);
    const [topFlaws, setTopFlaws] = useState<FlawData[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    // Exécution au montage du composant côté client
    useEffect(() => {
        const fetchData = async () => {
            try {
                setLoading(true);
                // On effectue les deux requêtes HTTP en parallèle pour gratter de la performance
                const [statsRes, flawsRes] = await Promise.all([
                    fetch("http://localhost:8000/api/stats"),
                    fetch("http://localhost:8000/api/top-flaws"),
                ]);

                if (!statsRes.ok || !flawsRes.ok) {
                    throw new Error("L'API backend est injoignable ou renvoie une erreur.");
                }

                const statsData: StatsData = await statsRes.json();
                const flawsData: FlawData[] = await flawsRes.json();

                setStats(statsData);
                setTopFlaws(flawsData);
            } catch (err: any) {
                setError(err.message || "Une erreur inconnue est survenue");
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    // Vue intermédiaire de chargement
    if (loading) {
        return (
            <div className="min-h-screen bg-neutral-50 flex items-center justify-center font-sans">
                <div className="text-xl flex flex-col items-center gap-4 text-neutral-500 font-semibold animate-pulse">
                    <div className="w-10 h-10 border-4 border-neutral-300 border-t-indigo-600 rounded-full animate-spin"></div>
                    Chargement du Dashboard...
                </div>
            </div>
        );
    }

    // Vue d'erreur
    if (error) {
        return (
            <div className="min-h-screen bg-neutral-50 flex items-center justify-center p-4 font-sans">
                <div className="bg-red-50 text-red-700 p-8 rounded-2xl shadow-sm border border-red-200 max-w-lg text-center">
                    <h2 className="text-3xl font-bold mb-3">Erreur de connexion</h2>
                    <p className="font-medium text-red-600 mb-6">{error}</p>
                    <div className="text-sm bg-white p-4 rounded-xl border border-red-100 text-left text-neutral-600 space-y-2">
                        <p><strong>Aide au débug :</strong></p>
                        <ul className="list-disc list-inside">
                            <li>L'API FastAPI est-elle lancée sur <code className="bg-neutral-100 px-1 py-0.5 rounded">http://localhost:8000</code> ?</li>
                            <li>Avez-vous bien mis <code className="bg-neutral-100 px-1 py-0.5 rounded">allow_origins=["*"]</code> dans le CORS ?</li>
                        </ul>
                    </div>
                </div>
            </div>
        );
    }

    // Écran principal
    return (
        <div className="min-h-screen bg-neutral-50 text-neutral-800 p-8 font-sans selection:bg-indigo-100 selection:text-indigo-900">
            <div className="max-w-6xl mx-auto space-y-10">

                {/* En-tête de page */}
                <header>
                    <h1 className="text-4xl font-extrabold text-neutral-900 tracking-tight">
                        Customer Intelligence
                    </h1>
                    <p className="text-neutral-500 mt-2 text-lg font-medium">
                        Analyse IA des retours utilisateurs en temps réel
                    </p>
                </header>

                {/* --- CARDS DE KPI --- */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="bg-white rounded-3xl shadow-[0_2px_20px_-8px_rgba(0,0,0,0.1)] border border-neutral-100 p-8 flex flex-col justify-center transition-transform hover:-translate-y-1 duration-300">
                        <h3 className="text-neutral-400 text-sm font-bold uppercase tracking-widest mb-3">
                            Total des avis analysés
                        </h3>
                        <div className="text-6xl font-black text-indigo-600 tracking-tighter">
                            {stats?.total_feedbacks.toLocaleString("fr-FR")}
                        </div>
                        <div className="mt-2 text-sm text-indigo-600/70 font-medium">
                            Avis correctement traités
                        </div>
                    </div>

                    <div className="bg-white rounded-3xl shadow-[0_2px_20px_-8px_rgba(0,0,0,0.1)] border border-neutral-100 p-8 flex flex-col justify-center transition-transform hover:-translate-y-1 duration-300">
                        <h3 className="text-neutral-400 text-sm font-bold uppercase tracking-widest mb-3">
                            Score moyen global
                        </h3>
                        <div className="flex items-baseline gap-2">
                            <span className={`text-6xl font-black tracking-tighter ${(stats?.score_moyen ?? 0) >= 0 ? 'text-emerald-500' : 'text-rose-500'
                                }`}>
                                {(stats?.score_moyen ?? 0) > 0 ? "+" : ""}
                                {stats?.score_moyen !== undefined ? stats.score_moyen : "-"}
                            </span>
                            <span className="text-neutral-300 font-bold text-2xl tracking-tighter">/ 5</span>
                        </div>
                        <div className="mt-2 text-sm text-neutral-400 font-medium">
                            {((stats?.score_moyen ?? 0) >= 0 ? "Sentiment majoritairement positif" : "Alerte : Sentiment négatif dominant")}
                        </div>
                    </div>
                </div>

                {/* --- GRAPHIQUE RECHARTS --- */}
                <div className="bg-white rounded-3xl shadow-[0_2px_20px_-8px_rgba(0,0,0,0.1)] border border-neutral-100 p-8 overflow-hidden">
                    <div className="mb-8">
                        <h2 className="text-2xl font-extrabold text-neutral-900 tracking-tight">
                            Alerte: Pires catégories
                        </h2>
                        <p className="text-neutral-500 text-sm mt-1 font-medium">
                            Défauts récurrents pénalisant l'expérience (&ge; 5 occurrences)
                        </p>
                    </div>

                    {topFlaws.length === 0 ? (
                        <div className="flex justify-center items-center h-72 text-neutral-400 italic bg-neutral-50/50 rounded-2xl border border-dashed border-neutral-200">
                            Absence de données (ou volume par catégorie insuffisant).
                        </div>
                    ) : (
                        <div className="h-80 w-full mt-4">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart
                                    data={topFlaws}
                                    margin={{ top: 20, right: 30, left: 0, bottom: 5 }}
                                >
                                    <CartesianGrid strokeDasharray="4 4" vertical={false} stroke="#E5E7EB" />
                                    <XAxis
                                        dataKey="categorie_macro"
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fill: '#6B7280', fontSize: 13, fontWeight: 600 }}
                                        dy={16}
                                    />
                                    <YAxis
                                        // Axe Y forcé de -5 à 0 pour bien illustrer les scores négatifs, 
                                        // ou de -5 à 5 selon ta préférence.
                                        domain={[-5, 5]}
                                        axisLine={false}
                                        tickLine={false}
                                        tick={{ fill: '#9CA3AF', fontWeight: 500 }}
                                        dx={-10}
                                    />
                                    <Tooltip
                                        cursor={{ fill: '#F9FAFB' }}
                                        contentStyle={{
                                            borderRadius: '16px',
                                            border: '1px solid #F3F4F6',
                                            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                                            padding: '16px',
                                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                                            backdropFilter: 'blur(8px)'
                                        }}
                                        labelStyle={{ fontWeight: '800', color: '#111827', marginBottom: '8px', textTransform: 'capitalize' }}
                                        formatter={(value: number, name: string, props: any) => [
                                            <span key="score" className="font-bold text-rose-600">{value} / 5</span>,
                                            'Score moyen'
                                        ]}
                                    />
                                    <Bar
                                        dataKey="score_moyen"
                                        fill="#F43F5E"
                                        // Coins arrondis sympas sur les barres
                                        radius={[8, 8, 8, 8]}
                                        barSize={48}
                                        // Animation native Recharts au chargement
                                        isAnimationActive={true}
                                        animationDuration={1500}
                                        animationEasing="ease-out"
                                    />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
