export interface TableSnapshot { headers: string[]; rows: string[][] }
function cellText(cell: Element) {
  const copy = cell.cloneNode(true) as HTMLElement;
  copy.querySelectorAll('button.record-title').forEach(node => node.replaceWith(document.createTextNode(node.textContent ?? '')));
  copy.querySelectorAll('button, input, select, textarea, svg, .ant-select, .ant-typography-copy, .ant-table-column-sorters .ant-table-column-sorter, .ant-table-filter-trigger, [aria-hidden="true"]').forEach(node => node.remove());
  return (copy.textContent ?? '').replace(/\s+/g, ' ').trim();
}
/** Export only rendered cells: never serialize hidden API fields or masked secrets. */
export function readTable(table: HTMLTableElement): TableSnapshot {
  const grid: string[][] = [];
  Array.from(table.tHead?.rows ?? []).forEach((row, y) => {
    grid[y] ??= [];
    let x = 0;
    for (const cell of Array.from(row.cells)) {
      while (grid[y][x] !== undefined) x++;
      for (let dy = 0; dy < cell.rowSpan; dy++) {
        grid[y + dy] ??= [];
        for (let dx = 0; dx < cell.colSpan; dx++) grid[y + dy][x + dx] = cellText(cell);
      }
      x += cell.colSpan;
    }
  });
  const count = Math.max(0, ...grid.map(row => row.length));
  const allHeaders = Array.from({ length: count }, (_, x) => [...new Set(grid.map(row => row[x]).filter(Boolean))].join(' / '));
  const keep = allHeaders.map((name, i) => ({ name, i })).filter(({ name }) => name && !/^(aç(?:ão|ões)|selecionar|vincular receita)$/i.test(name));
  const rows = Array.from(table.tBodies).flatMap(body => Array.from(body.rows))
    .filter(row => !row.matches('.ant-table-measure-row, .ant-table-placeholder') && !row.querySelector('td[colspan]'))
    .map(row => keep.map(({ i }) => row.cells[i]?.classList.contains('print-hidden') ? '' : row.cells[i] ? cellText(row.cells[i]) : ''));
  return { headers: keep.map(({ name }) => name), rows };
}
export function tableCsv({ headers, rows }: TableSnapshot) {
  const cell = (value: string) => '"' + (/^[\s]*[=+\-@]/.test(value) || /^[\t\r\n]/.test(value) ? "'" + value : value).replace(/"/g, '""') + '"';
  return '\uFEFF' + [headers, ...rows].map(row => row.map(cell).join(';')).join('\r\n');
}
export function downloadTable(snapshot: TableSnapshot, title: string) {
  const url = URL.createObjectURL(new Blob([tableCsv(snapshot)], { type: 'text/csv;charset=utf-8' }));
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = (title.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9]+/g, '-').slice(0, 100) || 'tabela') + '.csv';
  document.body.append(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
