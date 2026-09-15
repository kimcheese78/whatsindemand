import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import MobileDataCards from './MobileDataCards';

const items = [
  { id: 1, name: 'Acme', jobs: 42 },
  { id: 2, name: 'Globex', jobs: 18 },
];

test('expands one dense-data card at a time on touch layouts', () => {
  render(
    <MobileDataCards
      items={items}
      getKey={(item) => item.id}
      getLabel={(item) => `${item.name}, ${item.jobs} jobs`}
      renderSummary={(item) => <span>{item.name}</span>}
      renderDetails={(item) => <p>{item.jobs} current openings</p>}
    />
  );

  const acme = screen.getByRole('button', { name: 'Acme, 42 jobs' });
  const globex = screen.getByRole('button', { name: 'Globex, 18 jobs' });

  expect(acme).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByText('42 current openings')).not.toBeInTheDocument();

  fireEvent.click(acme);
  expect(acme).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByText('42 current openings')).toBeInTheDocument();

  fireEvent.click(globex);
  expect(acme).toHaveAttribute('aria-expanded', 'false');
  expect(globex).toHaveAttribute('aria-expanded', 'true');
  expect(screen.queryByText('42 current openings')).not.toBeInTheDocument();
  expect(screen.getByText('18 current openings')).toBeInTheDocument();
});

test('provides full-width touch targets without exposing desktop cards', () => {
  render(
    <MobileDataCards
      items={items.slice(0, 1)}
      getKey={(item) => item.id}
      getLabel={(item) => item.name}
      renderSummary={(item) => <span>{item.name}</span>}
      renderDetails={() => null}
    />
  );

  const list = screen.getByRole('list');
  const trigger = screen.getByRole('button', { name: 'Acme' });

  expect(list).toHaveClass('lg:hidden');
  expect(trigger).toHaveClass('w-full', 'min-h-11');
});

test('reports the expanded item so its parent can load detail data', () => {
  const Harness = () => {
    const [selected, setSelected] = useState(null);
    return (
      <>
        <output>{selected?.name || 'none selected'}</output>
        <MobileDataCards
          items={items}
          getKey={(item) => item.id}
          getLabel={(item) => item.name}
          renderSummary={(item) => <span>{item.name}</span>}
          renderDetails={() => null}
          onExpandedChange={setSelected}
        />
      </>
    );
  };

  render(<Harness />);
  fireEvent.click(screen.getByRole('button', { name: 'Acme' }));
  expect(screen.getByText('Acme', { selector: 'output' })).toBeInTheDocument();

  fireEvent.click(screen.getByRole('button', { name: 'Acme' }));
  expect(screen.getByText('none selected', { selector: 'output' })).toBeInTheDocument();
});
