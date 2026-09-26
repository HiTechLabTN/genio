import { PortalLayout } from "../PortalLayout";
import { ActionButton, Badge, Card, CodeBlock, Section } from "../ui";
import productData from "../../product-data.json";

type Platform = { id: string; label: string; arch: string; status: "supported" | "unavailable"; how?: string; reason?: string };

function detect(): string {
  if (typeof navigator === "undefined") return "unknown";
  const ua = navigator.userAgent.toLowerCase();
  const mobile = /android|iphone|ipad/.test(ua);
  if (/android/.test(ua)) return "android";
  if (/win/.test(navigator.platform.toLowerCase()) || /win/.test(ua)) return "windows";
  if (/mac/.test(ua)) return "macos";
  if (/linux/.test(ua)) return mobile ? "mobile-linux" : "linux";
  return mobile ? "mobile" : "unknown";
}

export default function DownloadCenter() {
  const pd = productData as {
    version: string; artifacts: Record<string, string>;
    platforms: Record<string, { status: string; reason?: string; arch?: string[]; method?: string; image?: string }>;
  };
  const detected = detect();
  const cards: Platform[] = [
    { id: "linux", label: "Linux", arch: "x86_64 / aarch64", status: "supported", how: `curl -fsSL https://raw.githubusercontent.com/HiTechLabTN/genio/main/installer/bootstrap/install.sh | GENIO_REF=v${pd.version} bash` },
    { id: "docker", label: "Docker", arch: "linux/amd64", status: "supported", how: `docker pull ${pd.artifacts.docker}\ndocker run -p 8080:8080 ${pd.artifacts.docker}` },
    { id: "server", label: "Server (archive)", arch: "any Linux", status: "supported", how: `curl -fsSL -o genio-${pd.version}.tar.gz ${pd.artifacts.archive}\nsha256sum -c genio-${pd.version}.tar.gz.sha256` },
    { id: "windows", label: "Windows", arch: "x64", status: "unavailable", reason: pd.platforms.windows?.reason ?? "No signed EXE published" },
    { id: "macos", label: "macOS", arch: "arm64/x64", status: "unavailable", reason: pd.platforms.macos?.reason ?? "No signed DMG published" },
    { id: "android", label: "Android", arch: "aarch64", status: "unavailable", reason: pd.platforms.android?.reason ?? "Release signing required" },
  ];
  return (
    <PortalLayout title="Download" description="Get Genio: Linux, Docker, server archive. Only real published artifacts." path="/download">
      <Section title="Download Genio" sub={`Version ${pd.version}. Detected platform: ${detected} (manual choice always allowed).`}>
        <div className="grid gap-4 md:grid-cols-2">
          {cards.map((c) => (
            <Card key={c.id} label={`${c.label} download`}>
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-white">{c.label}</h3>
                {c.status === "supported"
                  ? <Badge tone="ok">AVAILABLE</Badge>
                  : <Badge tone="neutral">NOT AVAILABLE</Badge>}
              </div>
              <p className="mt-1 font-mono text-[11px] text-white/50">{c.arch}</p>
              {c.status === "supported" && c.how ? (
                <div className="mt-3"><CodeBlock code={c.how} label="install command" /></div>
              ) : (
                <p className="mt-3 text-xs text-white/60">
                  Build currently unavailable — {c.reason}. No fake download button is shown.
                </p>
              )}
            </Card>
          ))}
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <ActionButton href={pd.artifacts.base}>Release page v{pd.version}</ActionButton>
          <ActionButton href={pd.artifacts.checksum}>SHA-256 checksum</ActionButton>
        </div>
      </Section>
    </PortalLayout>
  );
}
