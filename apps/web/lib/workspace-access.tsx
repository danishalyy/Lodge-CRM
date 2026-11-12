"use client";
import { getActiveUserId, getActiveLodgeId } from "./api";
import { createContext, useContext, useRef, useEffect } from "react";
export type WorkspaceAccess = {
  contextId?: string;
  readOnly?: boolean;
  displayName?: string;
  roleKey?: string;
  lodgeName?: string;
  features: readonly string[];
  permissions: readonly string[];
  platform: boolean;
};
export const WorkspaceAccessContext = createContext<WorkspaceAccess>({
  features: [],
  permissions: [],
  platform: false,
});
export function useWorkspaceAccess() {
  const value = useContext(WorkspaceAccessContext);
  const scopeKey = JSON.stringify([
    value.contextId,
    value.platform,
    Boolean(value.readOnly),
    value.features,
    value.permissions,
  ]);
  const currentScope = useRef(scopeKey),
    mounted = useRef(true);
  currentScope.current = scopeKey;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  return {
    scopeKey,
    readOnly: value.platform || Boolean(value.readOnly),
    displayName: value.displayName,
    roleKey: value.roleKey,
    lodgeName: value.lodgeName,
    isCurrent: () =>
      mounted.current &&
      !localStorage.getItem("safarios_local_signout") &&
      currentScope.current === scopeKey &&
      (!value.contextId ||
        value.contextId === `${getActiveUserId()}:${getActiveLodgeId()}`),
    feature: (key: string) => !value.platform && value.features.includes(key),
    permission: (key: string) =>
      !value.platform && value.permissions.includes(key),
  };
}
