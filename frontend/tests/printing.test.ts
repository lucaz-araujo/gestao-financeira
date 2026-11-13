import { afterEach, describe, expect, it, vi } from 'vitest';
import { printSheet } from '../src/components/PrintLayout';
afterEach(() => { window.dispatchEvent(new Event('afterprint')); document.body.innerHTML = ''; vi.restoreAllMocks(); });
describe('impressão de uma folha por vez', () => {
  it('seleciona somente o documento solicitado e seus ancestrais', () => {
    document.body.innerHTML = '<main><aside>Menu</aside><section id="one" class="print-sheet">Um</section><section id="two" class="print-sheet">Dois</section></main>';
    const print = vi.spyOn(window, 'print').mockImplementation(() => {});
    printSheet('one');
    expect(print).toHaveBeenCalledOnce();
    expect(document.querySelectorAll('[data-layout-print-target]')).toHaveLength(1);
    expect(document.getElementById('one')?.hasAttribute('data-layout-print-target')).toBe(true);
    expect(document.querySelector('main')?.hasAttribute('data-layout-print-ancestor')).toBe(true);
    printSheet('two');
    expect(document.getElementById('one')?.hasAttribute('data-layout-print-target')).toBe(false);
    expect(document.getElementById('two')?.hasAttribute('data-layout-print-target')).toBe(true);
  });
  it('restaura a interface ao encerrar a impressão sem apagar classes existentes', () => {
    document.body.innerHTML = '<main class="existing"><section id="doc" class="print-sheet">Dados</section></main>';
    vi.spyOn(window, 'print').mockImplementation(() => {}); printSheet('doc');
    window.dispatchEvent(new Event('afterprint'));
    expect(document.querySelector('[data-layout-print-target], [data-layout-print-ancestor]')).toBeNull();
    expect(document.body.classList.contains('layout-print-mode')).toBe(false);
    expect(document.querySelector('main')?.className).toBe('existing');
  });
  it('prioriza o documento aberto em relação ao relatório ao usar a impressão do navegador', () => {
    document.body.innerHTML = '<article class="print-sheet contract-printable" id="doc">Documento</article><section class="print-sheet" id="report">Relatório</section>';
    for (const node of document.querySelectorAll('.print-sheet')) vi.spyOn(node, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 800, 600));
    window.dispatchEvent(new Event('beforeprint'));
    expect(document.querySelector('[data-layout-print-target]')?.id).toBe('doc');
  });
  it('evita abrir uma impressão vazia se o documento tiver sido fechado', () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {}); printSheet('missing');
    expect(print).not.toHaveBeenCalled();
  });
});
