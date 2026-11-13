/* Somente os dados já disponíveis na consulta assinada. */
document.getElementById('export-public-notes')?.addEventListener('click', () => {
  const rows = [...document.querySelectorAll('.print-native-table tr')].filter(row => !row.querySelector('td[colspan]'));
  const escape = value => '"' + (/^\s*[=+\-@]/.test(value) ? "'" + value : value).replace(/"/g, '""') + '"';
  const csv = '\uFEFF' + rows.map(row => [...row.cells].map(cell => escape(cell.textContent.trim())).join(';')).join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = 'notas-fiscais.csv';
  document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
