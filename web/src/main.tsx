import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { InfrastructureSmoke } from './smoke/InfrastructureSmoke';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <InfrastructureSmoke />
  </StrictMode>,
);
