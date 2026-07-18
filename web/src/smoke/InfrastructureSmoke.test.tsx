import { render, screen } from '@testing-library/react';

import { InfrastructureSmoke } from './InfrastructureSmoke';

describe('test infrastructure smoke', () => {
  it('renders a non-empty application root', () => {
    render(<InfrastructureSmoke />);

    expect(screen.getByTestId('infrastructure-smoke')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'loopflow' })).toBeVisible();
  });
});
