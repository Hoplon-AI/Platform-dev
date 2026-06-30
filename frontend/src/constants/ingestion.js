export const FILE_FORMAT_COLOR = {
  xls: "#1D7A4C",
  csv: "#2F6FB0",
  pdf: "#C0392B",
  doc: "#6B7280",
};

export const stageCopy = {
  SOV: {
    title: "Upload Schedule of Values",
    subtitle: "Start here. This creates the portfolio, properties, and block records used by later evidence uploads.",
    formats: "Excel (.xlsx / .xls) or CSV",
    badge: "Required first",
    explainer: "Creates the portfolio — properties, blocks and sums insured — that every later upload attaches to.",
  },
  FRA: {
    title: "Upload FRA evidence",
    subtitle: "Attach Fire Risk Assessment PDFs to the blocks created from the SoV upload.",
    formats: "PDF only",
    badge: "Requires SoV",
    explainer: "AI extracts risk ratings, fire safety measures and outstanding actions, matched to each block.",
  },
  FRAEW: {
    title: "Upload FRAEW evidence",
    subtitle: "Attach external wall fire review reports after the SoV has loaded the block data.",
    formats: "PDF only",
    badge: "Requires SoV",
    explainer: "Captures cladding, insulation and external wall risks for building-level fire scoring.",
  },
};

export const railTitles = {
  SOV: "Schedule of Values",
  FRA: "Fire Risk Assessment",
  FRAEW: "External Wall Review",
};

export const STAGES = ["SOV", "FRA", "FRAEW"];

export const pipelineStepsByStage = {
  SOV: [
    "Uploading file",
    "Validating format",
    "Parsing property schedule",
    "Detecting blocks",
    "Building portfolio",
    "Preparing dashboard",
    "Complete",
  ],
  FRA: [
    "Uploading document",
    "Extracting text from PDF",
    "Running AI analysis",
    "Identifying fire risk factors",
    "Scoring risk rating",
    "Saving to portfolio",
    "Complete",
  ],
  FRAEW: [
    "Uploading document",
    "Extracting text from PDF",
    "Running AI analysis",
    "Identifying cladding & wall risks",
    "Scoring building risk",
    "Saving to portfolio",
    "Complete",
  ],
};
