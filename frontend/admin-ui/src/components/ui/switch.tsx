import * as React from "react"
import * as SwitchPrimitive from "@radix-ui/react-switch"

import { cn } from "../../lib/utils"

function Switch({
  className,
  ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root>) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      className={cn(
        // Base styling with explicit colors and sizes
        "inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
        "disabled:cursor-not-allowed disabled:opacity-50",
        // Checked state - use direct color values
        "data-[state=checked]:bg-blue-500 data-[state=checked]:border-blue-500",
        // Unchecked state - gray background
        "data-[state=unchecked]:bg-gray-200 dark:data-[state=unchecked]:bg-gray-700",
        // Hover states
        "hover:data-[state=unchecked]:bg-gray-300 dark:hover:data-[state=unchecked]:bg-gray-600",
        className
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className={cn(
          // Thumb styling with explicit positioning
          "pointer-events-none block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform",
          // Position transforms - adjust for new sizing
          "data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0",
          // Ensure visibility
          "drop-shadow-md"
        )}
      />
    </SwitchPrimitive.Root>
  )
}

export { Switch }
