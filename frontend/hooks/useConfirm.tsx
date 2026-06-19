"use client";

import { useCallback, useRef, useState } from "react";

import { ConfirmDialog, type ConfirmOptions } from "@/components/ConfirmDialog";

interface PendingConfirm extends ConfirmOptions {
  resolve: (confirmed: boolean) => void;
}

export function useConfirm() {
  const [pending, setPending] = useState<ConfirmOptions | null>(null);
  const pendingRef = useRef<PendingConfirm | null>(null);

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      const next: PendingConfirm = { ...options, resolve };
      pendingRef.current = next;
      setPending(options);
    });
  }, []);

  const handleConfirm = useCallback(() => {
    pendingRef.current?.resolve(true);
    pendingRef.current = null;
    setPending(null);
  }, []);

  const handleCancel = useCallback(() => {
    pendingRef.current?.resolve(false);
    pendingRef.current = null;
    setPending(null);
  }, []);

  const dialog = (
    <ConfirmDialog
      open={pending !== null}
      options={pending}
      onConfirm={handleConfirm}
      onCancel={handleCancel}
    />
  );

  return { confirm, dialog };
}
