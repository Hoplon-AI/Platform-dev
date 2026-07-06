import { useMemo } from "react";
import {
  summariseBlockRisk,
  assessmentStatus,
  inDateTip,
  bandVerdict,
  bandClass,
  blockDisplayAddress,
  computeBlockAlerts,
  getFireRiskBand,
  getFireDocumentRisk,
  fraActionStats,
  getWallTypes,
  heightCategory,
  fmtMoney,
  fmt,
  titleCase,
  boolLabel,
  isPresent,
} from "../../utils/blockModel";
import { G } from "../../constants/glossary";
import {
  Tip,
  Pill,
  InDateBadge,
  Chip,
  StatTile,
  KV,
  Section,
  ChipRow,
  SubHead,
} from "./primitives";
import ProvenanceCard from "./ProvenanceCard";
import { ActionList } from "./ActionCard";
import { ConfidenceBadge, WarningsPanel, SourceMark } from "./Citations";
import { isLowConfidence } from "./citationsModel";

// Wrap a KV value with its source mark; value untouched when there is
// nothing to cite, so KV's own "—" placeholder behaviour is preserved.
// Low-confidence fields (< 70% or unverifiable) are highlighted red.
const withCite = (value, cite) => {
  if (value === null || value === undefined || value === "" || !cite) return value;
  const low = isLowConfidence(cite);
  return (
    <>
      {low ? (
        <span style={{
          color: "#991b1b", background: "#fef2f2", border: "1px solid #fecaca",
          borderRadius: 6, padding: "1px 6px",
        }}>
          {value}
        </span>
      ) : (
        value
      )}
      <SourceMark cite={cite} />
    </>
  );
};

export default function Dossier({ block }) {
  const fra = block.latest_fra;
  const fraew = block.latest_fraew;
  const { band: overall, reasons } = useMemo(() => summariseBlockRisk(block), [block]);
  const { street, postcode } = blockDisplayAddress(block);
  const alerts = useMemo(() => computeBlockAlerts(block), [block]);
  const stats = useMemo(() => fraActionStats(fra), [fra]);
  const fraewStats = useMemo(() => fraActionStats(fraew), [fraew]);
  const wallTypes = useMemo(() => getWallTypes(fraew), [fraew]);
  const fraStatus = useMemo(() => assessmentStatus(fra), [fra]);
  const fraewStatus = useMemo(() => assessmentStatus(fraew), [fraew]);

  const hCat = heightCategory(block.maxHeight) || (fraew?.building_height_category && titleCase(fraew.building_height_category));
  const fraBand = getFireRiskBand(fra);
  const fraewBand = getFireRiskBand(fraew);
  const bandColor = { Red: "#ef4444", Amber: "#f59e0b", Green: "#10b981" }[overall] || "#94a3b8";
  const toneOf = (b) => ({ Red: "red", Amber: "amber", Green: "green" }[b] || "default");
  const alertTone = {
    red: { bg: "#fef2f2", bd: "#fecaca", fg: "#991b1b" },
    amber: { bg: "#fffbeb", bd: "#fde68a", fg: "#92400e" },
    info: { bg: "#eff6ff", bd: "#bfdbfe", fg: "#1e40af" },
  };
  const sortedAlerts = [...alerts].sort((a, b) => ({ red: 0, amber: 1, info: 2 }[a.tone] - { red: 0, amber: 1, info: 2 }[b.tone]));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Hero */}
      <div className="card" style={{ borderLeft: `5px solid ${bandColor}` }}>
        <div className="card-body">
          <div className="row-between" style={{ alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.02em", lineHeight: 1.15 }}>{street}</div>
              <div style={{ color: "var(--muted)", marginTop: 4, fontSize: 14 }}>
                Block {block.name}{postcode ? ` · ${postcode}` : ""}{block.parent_uprn ? ` · UPRN ${block.parent_uprn}` : ""}
              </div>
            </div>
            <Tip text={G.overall}>
              <span className={`pill ${bandClass(overall)}`} style={{ fontSize: 13, padding: "8px 14px", cursor: "help" }}>{bandVerdict(overall)}</span>
            </Tip>
          </div>

          {/* Why */}
          <div style={{ marginTop: 12, fontSize: 13.5, color: "var(--text-light, #475569)", background: "var(--panel-soft, #f8fafc)", border: "1px solid var(--border-soft, #eef2f7)", borderRadius: 10, padding: "10px 12px" }}>
            {reasons.length ? (
              <><b style={{ color: "var(--text)" }}>Driven by:</b> {reasons.join(" · ")}</>
            ) : (
              <>No significant fire-risk concerns recorded for this block.</>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 10, marginTop: 16 }}>
            <StatTile label="Units" value={block.count} />
            <StatTile label="Max height" value={block.maxHeight > 0 ? `${fmt(block.maxHeight, 1)} m` : "—"} sub={hCat || undefined} />
            <StatTile label="Total insured" value={`£${fmtMoney(block.totalValue)}`} tip={G.tiv} tipAlign="right" />
            <StatTile label="FRA" value={fra ? fraBand : "None"} tone={toneOf(fraBand)} tip={G.fra} tipAlign="right" />
            <StatTile label="FRAEW" value={fraew ? fraewBand : "None"} tone={toneOf(fraewBand)} tip={G.fraew} tipAlign="right" />
            <StatTile label="Overdue actions" value={stats.overdue} tone={stats.overdue > 0 ? "red" : "default"} tip={G.overdueActions} tipAlign="right" />
          </div>
        </div>
      </div>

      {/* Alerts */}
      <div className="card">
        <div className="card-body">
          <div className="card-title" style={{ marginBottom: 10 }}>Risk flags</div>
          {sortedAlerts.length === 0 ? (
            <div style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "#166534", fontWeight: 600, fontSize: 14 }}>✓ No critical flags identified.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {sortedAlerts.map((a, i) => {
                const t = alertTone[a.tone] || alertTone.info;
                return (
                  <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", background: t.bg, border: `1px solid ${t.bd}`, color: t.fg, borderRadius: 10, padding: "9px 12px", fontSize: 13, fontWeight: 600 }}>
                    <span style={{ fontWeight: 800 }}>{a.tone === "info" ? "ⓘ" : "⚠"}</span>
                    <span>{a.text}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Building & construction */}
      <Section title="Building & construction" subtitle="Physical characteristics from the SoV + enrichment" defaultOpen>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "0 24px" }}>
          <div>
            <KV label="Units" value={block.count} />
            <KV label="Max height" value={block.maxHeight > 0 ? `${fmt(block.maxHeight, 1)} m` : "—"} />
            <KV label="Height category" value={hCat} />
            <KV label="Max storeys" value={block.maxStoreys > 0 ? block.maxStoreys : "—"} />
            <KV label="Build year" value={block.buildYear} />
          </div>
          <div>
            <KV label="Total insured value" value={`£${fmtMoney(block.totalValue)}`} tip={G.tiv} />
            <KV label="Listed building" value={block.isListed ? `Yes${block.listedGrade ? ` (Grade ${block.listedGrade})` : ""}` : "No"} tip={G.listed} />
            <KV label="Parent UPRN" value={block.parent_uprn} />
            <KV label="Coordinates" value={block.hasValidCoords ? `${fmt(block.lat, 5)}, ${fmt(block.lon, 5)}` : "—"} />
          </div>
        </div>
      </Section>

      {/* FRA */}
      <Section
        title="Fire Risk Assessment (FRA)"
        subtitle="Internal / common-parts fire safety"
        defaultOpen
        accessory={
          <>
            <ConfidenceBadge doc={fra} />
            <span className={`pill ${bandClass(fraBand)}`}>{fra ? fraBand : "None"}</span>
          </>
        }
      >
        {!fra ? (
          <div className="muted">No FRA linked to this block.</div>
        ) : (
          <>
            <WarningsPanel warnings={fra.validation_warnings} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "0 24px" }}>
              <div>
                <KV label="Risk rating" value={withCite(getFireDocumentRisk(fra), fra.citations?.risk_rating)} />
                <KV label="Assessment type" value={fra.fra_assessment_type} tip={G.assessmentType} />
                <KV label="Assessment date" value={withCite(fra.assessment_date, fra.citations?.assessment_date)} />
                <KV label="Valid until" value={withCite(fra.assessment_valid_until, fra.citations?.assessment_valid_until)} />
                <KV label="In date" value={<InDateBadge status={fraStatus} />} tip={inDateTip(fraStatus)} />
              </div>
              <div>
                <KV label="Assessor" value={withCite(fra.assessor_name, fra.citations?.assessor_name)} />
                <KV label="Company" value={fra.assessor_company} />
                <KV label="Evacuation strategy" value={withCite(fra.evacuation_strategy ? titleCase(fra.evacuation_strategy) : null, fra.citations?.evacuation_strategy)} tip={G.evacuation} />
                <KV label="BSA 2022 applicable" value={boolLabel(fra.bsa_2022_applicable)} tip={G.bsa2022} />
                <KV label="MOR event noted" value={boolLabel(fra.mandatory_occurrence_noted)} tip={G.mor} />
              </div>
            </div>

            <SubHead tip={G.compartmentation}>Fire safety measures</SubHead>
            <ChipRow>
              <Chip label="Sprinklers" value={fra.has_sprinkler_system ?? fra.sprinkler_system} />
              <Chip label="Smoke detection" value={fra.has_smoke_detection ?? fra.smoke_detection} />
              <Chip label="Fire alarm" value={fra.has_fire_alarm_system ?? fra.fire_alarm_system} />
              <Chip label="Fire doors" value={fra.has_fire_doors ?? fra.fire_doors} />
              <Chip label="Compartmentation" value={fra.has_compartmentation ?? fra.compartmentation} tip={G.compartmentation} />
              <Chip label="Emergency lighting" value={fra.has_emergency_lighting} />
              <Chip label="Dry riser" value={fra.has_dry_riser} tip={G.dryRiser} />
              <Chip label="Wet riser" value={fra.has_wet_riser} tip={G.wetRiser} />
            </ChipRow>

            <SubHead>Remedial actions</SubHead>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10 }}>
              <StatTile label="Total" value={stats.total} tip={G.totalActions} />
              <StatTile label="Overdue" value={stats.overdue} tone={stats.overdue > 0 ? "red" : "default"} tip={G.overdueActions} />
              <StatTile label="No date" value={stats.noDate} tone={stats.noDate > 0 ? "amber" : "default"} tip={G.noDateActions} tipAlign="right" />
              <StatTile label="High priority" value={stats.high} tone={stats.high > 0 ? "amber" : "default"} tip={G.highActions} tipAlign="right" />
            </div>
            <ActionList items={stats.items} max={20} />
            {fra.summary ? <div style={{ marginTop: 12, fontSize: 13, color: "var(--text-light, #475569)" }}><b>Summary:</b> {fra.summary}</div> : null}
          </>
        )}
      </Section>

      {/* FRAEW */}
      <Section
        title="External Wall System (FRAEW)"
        subtitle="Cladding, insulation & PAS 9980 appraisal"
        defaultOpen
        accessory={
          <>
            <ConfidenceBadge doc={fraew} />
            <span className={`pill ${bandClass(fraewBand)}`}>{fraew ? fraewBand : "None"}</span>
          </>
        }
      >
        {!fraew ? (
          <div className="muted">No FRAEW linked to this block.</div>
        ) : (
          <>
            <WarningsPanel warnings={fraew.validation_warnings} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "0 24px" }}>
              <div>
                <KV label="Building risk rating" value={withCite(fraew.building_risk_rating ?? getFireDocumentRisk(fraew), fraew.citations?.building_risk_rating)} />
                <KV label="PAS 9980 compliant" value={withCite(boolLabel(fraew.pas_9980_compliant), fraew.citations?.pas_9980_compliant)} tip={G.pas9980} />
                <KV label="Clause 14 applied" value={boolLabel(fraew.clause_14_applied)} tip={G.clause14} />
                <KV label="Assessment date" value={withCite(fraew.assessment_date, fraew.citations?.assessment_date)} />
                <KV label="Valid until" value={fraew.assessment_valid_until} />
                <KV label="In date" value={<InDateBadge status={fraewStatus} />} tip={inDateTip(fraewStatus)} />
              </div>
              <div>
                <KV label="Building height" value={withCite(fraew.building_height_m ? `${fmt(fraew.building_height_m, 1)} m` : null, fraew.citations?.building_height_m)} />
                <KV label="Construction frame" value={fraew.construction_frame_type} />
                <KV label="Retrofit year" value={fraew.retrofit_year} />
                <KV label="Remediation required" value={boolLabel(fraew.has_remedial_actions ?? fraew.remediation_required)} />
                <KV label="Interim measures" value={boolLabel(fraew.interim_measures_required, "Required", "Not required")} />
                <KV label="Assessor" value={fraew.assessor_name} />
              </div>
            </div>

            <SubHead tip={G.combustible}>Cladding & insulation</SubHead>
            <ChipRow>
              <Chip label="Combustible cladding" value={fraew.has_combustible_cladding ?? fraew.combustible_cladding} hazard tip={G.combustible} />
              <Chip label="ACM" value={fraew.aluminium_composite_cladding} hazard tip={G.acm} />
              <Chip label="HPL" value={fraew.hpl_cladding_present} hazard tip={G.hpl} />
              <Chip label="Timber" value={fraew.timber_cladding_present} hazard />
              <Chip label="EPS" value={fraew.eps_insulation_present} hazard tip={G.eps} />
              <Chip label="PIR" value={fraew.pir_insulation_present} hazard tip={G.pir} />
              <Chip label="Phenolic" value={fraew.phenolic_insulation_present} hazard tip={G.phenolic} />
              <Chip label="Mineral wool" value={fraew.mineral_wool_insulation_present} tip={G.mineralWool} />
            </ChipRow>

            <SubHead tip={G.fireBreaks}>Protections & compliance</SubHead>
            <ChipRow>
              <Chip label="Cavity barriers" value={fraew.cavity_barriers_present} tip={G.cavityBarriers} />
              <Chip label="Fire breaks (floors)" value={fraew.fire_breaks_floor_level} tip={G.fireBreaks} />
              <Chip label="Fire breaks (party walls)" value={fraew.fire_breaks_party_walls} tip={G.fireBreaks} />
              <Chip label="BS 8414 evidence" value={fraew.bs8414_test_evidence} tip={G.bs8414} />
              <Chip label="BR 135 criteria" value={fraew.br135_criteria_met} tip={G.br135} />
              <Chip label="Dry riser" value={fraew.dry_riser_present} tip={G.dryRiser} />
              <Chip label="Wet riser" value={fraew.wet_riser_present} tip={G.wetRiser} />
            </ChipRow>

            <SubHead>Recommended further investigation</SubHead>
            <ChipRow>
              <Chip label="Height survey" value={fraew.height_survey_recommended} hazard tip={G.heightSurvey} />
              <Chip label="Fire door survey" value={fraew.fire_door_survey_recommended} hazard />
              <Chip label="Intrusive investigation" value={fraew.intrusive_investigation_recommended} hazard tip={G.intrusive} />
              <Chip label="Asbestos suspected" value={fraew.asbestos_suspected} hazard tip={G.asbestos} />
            </ChipRow>

            {wallTypes.length > 0 && (
              <>
                <SubHead>Wall types ({wallTypes.length})</SubHead>
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th>Ref</th><th>Description</th><th>Coverage</th><th>Insulation</th><th>Risk</th></tr></thead>
                    <tbody>
                      {wallTypes.map((w, i) => (
                        <tr key={i}>
                          <td>{w.type_ref ?? `Type ${i + 1}`}</td>
                          <td>{w.description ?? "—"}</td>
                          <td>{isPresent(w.coverage_percent) ? `${w.coverage_percent}%` : "—"}</td>
                          <td>{w.insulation_type ? titleCase(w.insulation_type) : "—"}</td>
                          <td>{w.overall_risk ? titleCase(w.overall_risk) : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
            {fraewStats.items.length > 0 && (
              <>
                <SubHead>Remedial actions</SubHead>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 10 }}>
                  <StatTile label="Total" value={fraewStats.total} tip={G.totalActions} />
                  <StatTile label="Overdue" value={fraewStats.overdue} tone={fraewStats.overdue > 0 ? "red" : "default"} tip={G.overdueActions} />
                  <StatTile label="No date" value={fraewStats.noDate} tone={fraewStats.noDate > 0 ? "amber" : "default"} tip={G.noDateActions} tipAlign="right" />
                  <StatTile label="High priority" value={fraewStats.high} tone={fraewStats.high > 0 ? "amber" : "default"} tip={G.highActions} tipAlign="right" />
                </div>
                <ActionList items={fraewStats.items} max={20} />
              </>
            )}
            {fraew.interim_measures_detail ? <div style={{ marginTop: 12, fontSize: 13, color: "var(--text-light, #475569)" }}><b>Interim measures:</b> {fraew.interim_measures_detail}</div> : null}
            {fraew.summary ? <div style={{ marginTop: 8, fontSize: 13, color: "var(--text-light, #475569)" }}><b>Summary:</b> {fraew.summary}</div> : null}
          </>
        )}
      </Section>

      {/* Properties */}
      <Section title="Properties in this block" subtitle={`${block.count} unit${block.count === 1 ? "" : "s"}`} accessory={<Pill>{block.count}</Pill>}>
        <div className="table-wrap" style={{ maxHeight: 420, overflowY: "auto" }}>
          <table className="table">
            <thead><tr><th>Address</th><th>UPRN</th><th>Sum insured</th><th>FRA</th><th>FRAEW</th></tr></thead>
            <tbody>
              {block.properties.map((p, i) => {
                // FRA/FRAEW are assessed at block level (common/internal areas), so
                // every unit in the block inherits the block's assessment when the
                // property doesn't carry its own.
                const propFra = p.latest_fra ?? block.latest_fra;
                const propFraew = p.latest_fraew ?? block.latest_fraew;
                const pf = getFireRiskBand(propFra);
                const pfe = getFireRiskBand(propFraew);
                return (
                  <tr key={p.id ?? p.property_reference ?? i}>
                    <td>{p.address_line_1 || p.address || p.property_reference || `Property ${i + 1}`}</td>
                    <td>{p.uprn ?? "—"}</td>
                    <td>£{fmtMoney(p.sum_insured)}</td>
                    <td>{propFra ? <span className={`pill ${bandClass(pf)}`}>{pf}</span> : "—"}</td>
                    <td>{propFraew ? <span className={`pill ${bandClass(pfe)}`}>{pfe}</span> : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Provenance */}
      <Section title="Data provenance" subtitle="Source documents & extraction confidence">
        {block.linkedDocs?.length ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {block.linkedDocs.map((d, i) => (
              <ProvenanceCard key={i} doc={d} />
            ))}
          </div>
        ) : (
          <div className="muted">No fire-risk documents linked to this block yet.</div>
        )}
      </Section>
    </div>
  );
}
