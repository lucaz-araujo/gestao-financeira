export interface Empresa { id: number; razao: string; cnpj: string }
export interface Session { id: number; username: string; nome: string; avatar?: string | null; uf: number | null; permissions: string[]; empresas: Empresa[] }
export interface Page<T> { count: number; results: T[]; next: string | null; previous: string | null }
export interface Row { id: number; descricao?: string; sigla?: string; tipo_produto?: 'P' | 'S'; valor?: string | null; instituicao?: string; cliente?: number; parceiro?: number | null; uf?: number | null; cidade?: number | null; cnpj?: string; ativo?: boolean; desativar?: boolean; [field: string]: unknown }
export type Resource = 'clientes' | 'parceiros' | 'liberacoes' | 'bloqueios' | 'produtos';
export interface Option { value: number; label: string }
