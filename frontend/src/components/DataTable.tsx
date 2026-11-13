import { Table as AntTable, Button, Space, type TableProps } from 'antd';
import { DownloadOutlined, PrinterOutlined } from '@ant-design/icons';
import { useEffect, useId, useRef, useState } from 'react';
import { createPortal, flushSync } from 'react-dom';
import { PrintHeader, PrintFooter, printSheet } from './PrintLayout';
import { downloadTable, readTable, type TableSnapshot } from '../utils/tableExport';

export function Table<RecordType extends object = Record<string, unknown>>(props: TableProps<RecordType> & { exportTitle?: string; tableActions?: boolean }) {
  const { exportTitle, tableActions = true, ...tableProps } = props;
  const root = useRef<HTMLDivElement>(null);
  const id = useId();
  const [snapshot, setSnapshot] = useState<(TableSnapshot & { title: string; scope: string }) | null>(null);
  useEffect(() => {
    const clear = () => setSnapshot(null);
    window.addEventListener('afterprint', clear);
    return () => window.removeEventListener('afterprint', clear);
  }, []);
  function capture() {
    const table = root.current?.querySelector<HTMLTableElement>('.ant-table-content table, .ant-table-body table, table');
    if (!table) return null;
    const result = readTable(table);
    const drawer = root.current?.closest('.ant-drawer');
    const section = root.current?.closest('section, .ant-card');
    const previous = root.current?.previousElementSibling;
    const heading = previous?.matches('h2, h3, h4, h5') ? previous : section?.querySelector('.print-header h1') ?? drawer?.querySelector('.ant-drawer-title') ?? section?.querySelector('.table-toolbar strong, .ant-card-head-title') ?? document.querySelector('.page-heading h1');
    const cleanHeading = heading?.cloneNode(true) as HTMLElement | undefined;
    cleanHeading?.querySelectorAll('.count-pill').forEach(node => node.remove());
    const title = exportTitle ?? cleanHeading?.textContent?.trim() ?? 'Tabela';
    const page = props.pagination && typeof props.pagination === 'object' ? props.pagination.current ?? Number(root.current?.querySelector('.ant-pagination-item-active')?.textContent ?? 1) : null;
    const countLabel = `${result.rows.length} ${result.rows.length === 1 ? 'registro exibido' : 'registros exibidos'}`;
    const scope = props.pagination === false ? countLabel : `Página ${page ?? 1} · ${countLabel}`;
    return { ...result, title, scope };
  }
  function print() {
    const result = capture(); if (!result?.rows.length) return;
    flushSync(() => setSnapshot(result));
    printSheet(id);
  }
  const disabled = !!props.loading || !props.dataSource?.length;
  return <div className="data-table" ref={root}>
    {tableActions && <div className="table-export-actions print-hidden"><span>{props.pagination === false ? 'Dados exibidos' : 'Página atual'}</span><Space wrap>
      <Button icon={<PrinterOutlined/>} aria-label="Imprimir tabela" onClick={print} disabled={disabled}>Imprimir tabela</Button>
      <Button icon={<DownloadOutlined/>} aria-label="Exportar planilha (CSV)" disabled={disabled} onClick={() => { const result = capture(); if (result?.rows.length) downloadTable(result, result.title); }}>Exportar planilha (CSV)</Button>
    </Space></div>}
    <AntTable<RecordType> {...tableProps}/>
    {snapshot && createPortal(<article id={id} className="print-sheet print-landscape layout-print-only table-print-snapshot">
      <PrintHeader title={snapshot.title} subtitle={snapshot.scope} reference="Tabela"/>
      <table className="print-native-table"><thead><tr>{snapshot.headers.map((name, i) => <th key={i}>{name}</th>)}</tr></thead><tbody>{snapshot.rows.map((row, i) => <tr key={i}>{row.map((value, j) => <td key={j}>{value}</td>)}</tr>)}</tbody></table><PrintFooter/>
    </article>, document.body)}
  </div>;
}
