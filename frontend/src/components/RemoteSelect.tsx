import { Select } from 'antd';
import { useEffect, useState } from 'react';
import { api, errorMessage } from '../api';
import { useSession } from '../session';
import type { Option, Page, Row } from '../types';
interface Props { url: string; labelField?: string; value?: number | null; onChange?: (value?: number) => void; disabled?: boolean; placeholder?: string; id?: string }
export function RemoteSelect({ url, labelField = 'instituicao', value, onChange, ...props }: Props) {
  const { empresa } = useSession();
  const [search, setSearch] = useState('');
  const [options, setOptions] = useState<Option[]>([]);
  const [selected, setSelected] = useState<Option>();
  const [loading, setLoading] = useState(false);
  const [issue, setIssue] = useState('');
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      setLoading(true); setIssue('');
      api<Page<Row>>(url + (url.includes('?') ? '&' : '?') + new URLSearchParams({ search, page_size: '50' }), {}, empresa)
        .then(page => { if (active) setOptions(page.results.map(row => ({ value: row.id, label: String(row[labelField]) }))); })
        .catch(error => { if (active) setIssue(errorMessage(error)); }).finally(() => { if (active) setLoading(false); });
    }, 200);
    return () => { active = false; clearTimeout(timer); };
  }, [url, search, empresa, labelField]);
  useEffect(() => {
    let active = true;
    setSelected(undefined);
    if (!value) return;
    const isOptions = url.includes('/opcoes/');
    const detail = isOptions ? url + (url.includes('?') ? '&' : '?') + 'id=' + value : url.split('?')[0] + value + '/';
    api<Row | Page<Row>>(detail, {}, empresa).then(data => {
      const row = 'results' in data ? (data as Page<Row>).results[0] : data as Row;
      if (active && row) setSelected({ value: row.id, label: String(row[labelField]) });
    }).catch(error => { if (active) setIssue(errorMessage(error)); });
    return () => { active = false; };
  }, [value, url, empresa, labelField]);
  const all = selected && !options.some(o => o.value === selected.value) ? [selected, ...options] : options;
  return <Select {...props} value={value ?? undefined} onChange={onChange} allowClear showSearch
    filterOption={false} onSearch={setSearch} options={all} loading={loading} style={{ width: '100%' }}
    notFoundContent={issue || (loading ? 'Carregando…' : 'Nenhum resultado')} />;
}
