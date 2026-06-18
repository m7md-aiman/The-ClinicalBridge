import Link from "next/link";
import {
  ArrowRight,
  Clock,
  Database,
  HeartPulse,
  MessageSquareText,
  Quote,
  ShieldCheck,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/reveal";
import { ArchitectureDiagram } from "@/components/architecture-diagram";

const PILLARS = [
  {
    icon: <Database className="h-5 w-5" />,
    name: "EHR — the past",
    blurb: "Diagnoses, medications, labs, and notes accumulated over years.",
    stat: "~30% of hypertensive patients are missing the structured diagnosis code.",
  },
  {
    icon: <HeartPulse className="h-5 w-5" />,
    name: "RPM — the present",
    blurb: "Continuous vitals streaming from wearables and home devices.",
    stat: "Only 5–13% of ICU alarms are clinically actionable; 2% of patients cause 77% of false alarms.",
  },
  {
    icon: <MessageSquareText className="h-5 w-5" />,
    name: "Anamnesis — the voice",
    blurb: "The patient's own account: symptoms, lifestyle, adherence.",
    stat: "Often unstructured — in some systems it isn't stored in the EHR at all.",
  },
];

const SAFETY = [
  { icon: <ShieldCheck className="h-5 w-5" />, value: "0", label: "hallucinated citations" },
  { icon: <Quote className="h-5 w-5" />, value: "100%", label: "claims cited to a source" },
  { icon: <HeartPulse className="h-5 w-5" />, value: "100%", label: "scenario pass rate" },
  { icon: <Clock className="h-5 w-5" />, value: "~19s", label: "per brief (goal <60s)" },
];

export default function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="surface-grid border-b">
        <div className="mx-auto max-w-6xl px-4 py-20 md:py-28">
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-primary" />
              LLM-powered multi-agent clinical decision support
            </span>
          </Reveal>
          <Reveal delay={0.05}>
            <h1 className="mt-5 max-w-3xl text-4xl font-semibold leading-tight tracking-tight md:text-6xl">
              Bridging the <span className="text-primary">Clinical Context Gap</span>
            </h1>
          </Reveal>
          <Reveal delay={0.1}>
            <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
              ClinicalBridge synthesizes fragmented <strong>EHR</strong>, <strong>remote
              monitoring</strong>, and <strong>patient-reported</strong> data into a single, cited{" "}
              <strong>Clinical Context Brief</strong> a clinician can read in under 60 seconds.
            </p>
          </Reveal>
          <Reveal delay={0.15}>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/demo">
                <Button size="lg">
                  Try the interactive demo <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/evaluation">
                <Button size="lg" variant="outline">
                  See the evaluation
                </Button>
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* The Clinical Context Gap */}
      <section className="mx-auto max-w-6xl px-4 py-16">
        <Reveal>
          <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">
            Three data streams that never talk to each other
          </h2>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Clinicians have more data than ever, yet decisions are made with less meaningful
            context. ClinicalBridge reconnects the three pillars.
          </p>
        </Reveal>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {PILLARS.map((p, i) => (
            <Reveal key={p.name} delay={i * 0.08}>
              <Card className="h-full">
                <CardContent className="pt-6">
                  <div className="grid h-10 w-10 place-items-center rounded-xl bg-muted text-primary">
                    {p.icon}
                  </div>
                  <h3 className="mt-4 font-semibold">{p.name}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{p.blurb}</p>
                  <p className="mt-4 border-t pt-3 text-sm text-foreground/80">{p.stat}</p>
                </CardContent>
              </Card>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Architecture */}
      <section className="border-y bg-muted/20">
        <div className="mx-auto max-w-6xl px-4 py-16">
          <Reveal>
            <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">
              Four specialized agents, one orchestrated brief
            </h2>
            <p className="mt-2 max-w-2xl text-muted-foreground">
              A linear-then-convergent pipeline: triage decides urgency and what to retrieve, two
              agents gather context in parallel, and synthesis fuses everything into a cited brief.
            </p>
          </Reveal>
          <div className="mt-8">
            <Reveal delay={0.1}>
              <ArchitectureDiagram />
            </Reveal>
          </div>
        </div>
      </section>

      {/* Safety strip */}
      <section className="mx-auto max-w-6xl px-4 py-16">
        <Reveal>
          <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">
            Safe and grounded by construction
          </h2>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            In a high-stakes domain, every claim is traceable. Measured across all five clinical
            scenarios:
          </p>
        </Reveal>
        <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
          {SAFETY.map((s, i) => (
            <Reveal key={s.label} delay={i * 0.06}>
              <Card className="h-full">
                <CardContent className="pt-6">
                  <div className="text-primary">{s.icon}</div>
                  <div className="mt-3 text-3xl font-semibold tracking-tight">{s.value}</div>
                  <div className="text-sm text-muted-foreground">{s.label}</div>
                </CardContent>
              </Card>
            </Reveal>
          ))}
        </div>
        <Reveal delay={0.1}>
          <p className="mt-6 text-sm text-muted-foreground">
            Built with LangChain · ChromaDB (local embeddings) · OpenRouter · Pydantic-validated
            structured output. All patient data is fully simulated.
          </p>
        </Reveal>
      </section>
    </div>
  );
}
