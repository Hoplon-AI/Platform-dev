import { MotionConfig } from 'framer-motion';
import { ProcessingSteps } from 'equirisk-frontend';

const SOV_STEPS = [
  "Parsing headers",
  "Matching addresses",
  "Validating data",
  "Enriching UPRNs",
  "Complete",
];

const Wrapper = ({ children }) => (
  <MotionConfig reducedMotion="always">
    <div style={{ padding: 40, background: "var(--warm-bg)", borderRadius: 16 }}>
      {children}
    </div>
  </MotionConfig>
);

export const FirstStep = () => (
  <Wrapper>
    <ProcessingSteps steps={SOV_STEPS} currentIndex={0} />
  </Wrapper>
);

export const MidProgress = () => (
  <Wrapper>
    <ProcessingSteps steps={SOV_STEPS} currentIndex={2} />
  </Wrapper>
);

export const Complete = () => (
  <Wrapper>
    <ProcessingSteps steps={SOV_STEPS} currentIndex={4} />
  </Wrapper>
);
