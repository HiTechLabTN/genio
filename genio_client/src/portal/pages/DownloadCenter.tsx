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
    public_release: {
      tag: string; tarball: string; sha256: string; manifest: string;
      sbom: string; notes: string; docker: string;
      appimage: string; appimage_sha256: string; deb: string; deb_sha256: string;
    };
  };
  const detected = detect();
  const rel = pd.public_release;
  const cards: Platform[] = [
    { id: "appimage", label: `Linux AppImage (${rel.tag})`, arch: "x86_64", status: "supported", how: `curl -fsSL -o genio.AppImage ${rel.appimage}\ncurl -fsSL -o genio.AppImage.sha256 ${rel.appimage_sha256}\nsha256sum -c genio.AppImage.sha256` },
    { id: "deb", label: `Linux DEB (${rel.tag})`, arch: "amd64", status: "supported", how: `curl -fsSL -o genio.deb ${rel.deb}\nsha256sum genio.deb  # must match ${rel.deb_sha256}` },
    { id: "docker", label: "Docker", arch: "linux/amd64", status: "supported", how: `docker pull ${rel.docker}\ndocker run -p 8080:8080 ${rel.docker}` },
    { id: "installer", label: "CLI installer", arch: "any Linux", status: "supported", how: `curl -fsSL https://raw.githubusercontent.com/HiTechLabTN/genio/main/installer/bootstrap/install.sh | GENIO_REF=${rel.tag} bash` },
    { id: "server", label: `Server (source archive ${rel.tag})`, arch: "any Linux", status: "supported", how: `curl -fsSL -o genio.tar.gz ${rel.tarball}\nsha256sum -c genio.tar.gz.sha256  # from ${rel.sha256}` },
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
          <ActionButton href={rel.notes}>Release {rel.tag}</ActionButton>
          <ActionButton href={rel.manifest}>Release manifest</ActionButton>
          <ActionButton href={rel.sbom}>SBOM</ActionButton>
        </div>
      </Section>
    </PortalLayout>
  );
}
