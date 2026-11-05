import { useEffect, type RefObject } from 'react';

export function useModalDialogFocus(
  isOpen: boolean,
  dialogRef: RefObject<HTMLElement | null>
): void {
  useEffect(() => {
    if (!isOpen) return;
    const trigger = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current!;
    const controls = () => Array.from(dialog.querySelectorAll<HTMLElement>(
      'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'
    )).filter((element) => element.tabIndex >= 0 && element.getClientRects().length > 0);
    (controls()[0] ?? dialog).focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;
      const items = controls();
      const index = items.indexOf(document.activeElement as HTMLElement);
      if (!items.length) {
        event.preventDefault();
        dialog.focus();
      } else if (event.shiftKey && index <= 0) {
        event.preventDefault();
        items[items.length - 1]!.focus();
      } else if (!event.shiftKey && (index === -1 || index === items.length - 1)) {
        event.preventDefault();
        items[0]!.focus();
      }
    };
    dialog.addEventListener('keydown', onKeyDown);
    return () => {
      dialog.removeEventListener('keydown', onKeyDown);
      if (trigger?.isConnected) trigger.focus();
    };
  }, [isOpen, dialogRef]);
}
