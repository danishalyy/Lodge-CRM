"use client";
import { createContext, useContext } from "react";
export type WorkspaceAccess = {
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
  return {
    feature: (key: string) => value.features.includes(key),
    permission: (key: string) =>
      value.platform || value.permissions.includes(key),
  };
}
