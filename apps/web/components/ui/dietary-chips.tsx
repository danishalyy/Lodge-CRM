import { AlertTriangle, Leaf } from "lucide-react";
export function DietaryChips({
  allergies,
  dietary,
}: {
  allergies?: string;
  dietary?: string;
}) {
  if (!allergies && !dietary) return null;
  return (
    <div className="dietaryChips">
      {allergies && (
        <span className="dietaryChip allergy">
          <AlertTriangle size={14} />
          {allergies}
        </span>
      )}
      {dietary && (
        <span className="dietaryChip">
          <Leaf size={14} />
          {dietary}
        </span>
      )}
    </div>
  );
}
