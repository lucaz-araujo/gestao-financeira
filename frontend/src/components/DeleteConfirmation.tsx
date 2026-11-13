import { App } from 'antd';
import { useEffect, useRef, type ReactElement, type ReactNode } from 'react';

interface Props {
  title: ReactNode;
  description?: ReactNode;
  recordName?: string;
  children: ReactElement;
  onConfirm: () => void | Promise<unknown>;
  okText?: string;
  cancelText?: string;
}

/** Confirmação compartilhada das exclusões, com o contexto visual da aplicação. */
export function DeleteConfirmation({ title, description, recordName, children, onConfirm, okText = 'Excluir', cancelText = 'Cancelar' }: Props) {
  const { modal } = App.useApp();
  const dialog = useRef<ReturnType<typeof modal.confirm> | null>(null);
  useEffect(() => () => { dialog.current?.destroy(); }, []);
  function open() {
    if (dialog.current) return;
    dialog.current = modal.confirm({
      centered: true,
      title,
      content: <div>{recordName && <p><strong>Registro:</strong> {recordName}</p>}<p>{description ?? 'Deseja realmente excluir este registro?'}</p></div>,
      okText,
      cancelText,
      okButtonProps: { danger: true },
      autoFocusButton: 'cancel',
      maskClosable: false,
      onOk: () => onConfirm(),
      afterClose: () => { dialog.current = null; },
    });
  }
  return <span className="delete-confirm-trigger" onClick={open}>{children}</span>;
}
