// constants/UserSettings.tsx
import { chakra, IconProps } from "@chakra-ui/react";
import {
  ClockIcon,
  ExclamationCircleIcon,
  NoSymbolIcon,
  WifiIcon,
} from "@heroicons/react/24/outline";
import { DataLimitResetStrategy } from "../types/User";

/* --------------------------------------------------------- *
 *  1. Helper: turns any outline-icon into a Chakra component
 *     with the sizing you want.
 * --------------------------------------------------------- */
const iconDefaults: IconProps = { w: 4, h: 4, strokeWidth: 2 };

const makeStatusIcon = (Icon: React.ElementType) =>
  // a perfectly normal functional component – no special types needed
  (props: IconProps) =>
    <chakra.svg as={Icon} {...iconDefaults} {...props} />;

/* --------------------------------------------------------- *
 *  2. The actual icons
 * --------------------------------------------------------- */
const ActiveStatusIcon   = makeStatusIcon(WifiIcon);
const DisabledStatusIcon = makeStatusIcon(NoSymbolIcon);
const LimitedStatusIcon  = makeStatusIcon(ExclamationCircleIcon);
const ExpiredStatusIcon  = makeStatusIcon(ClockIcon);
const OnHoldStatusIcon   = makeStatusIcon(ClockIcon);

/* --------------------------------------------------------- *
 *  3. Reset strategies (unchanged)
 * --------------------------------------------------------- */
export const resetStrategy: { title: string; value: DataLimitResetStrategy }[] =
[
  { title: "No",       value: "no_reset" },
  { title: "Daily",    value: "day"      },
  { title: "Weekly",   value: "week"     },
  { title: "Monthly",  value: "month"    },
  { title: "Annually", value: "year"     },
];

/* --------------------------------------------------------- *
 *  4. Status-colour map – just use the function component type
 * --------------------------------------------------------- */
type StatusIcon = ReturnType<typeof makeStatusIcon>;

export const statusColors: Record<
  string,
  { statusColor: string; bandWidthColor: string; icon: StatusIcon }
> = {
  active:     { statusColor: "green",  bandWidthColor: "primary", icon: ActiveStatusIcon },
  connected:  { statusColor: "green",  bandWidthColor: "primary", icon: ActiveStatusIcon },
  disabled:   { statusColor: "gray",   bandWidthColor: "gray",    icon: DisabledStatusIcon },
  expired:    { statusColor: "orange", bandWidthColor: "orange",  icon: ExpiredStatusIcon },
  on_hold:    { statusColor: "purple", bandWidthColor: "purple",  icon: OnHoldStatusIcon },
  connecting: { statusColor: "orange", bandWidthColor: "orange",  icon: ExpiredStatusIcon },
  limited:    { statusColor: "red",    bandWidthColor: "red",     icon: LimitedStatusIcon },
  error:      { statusColor: "red",    bandWidthColor: "red",     icon: LimitedStatusIcon },
};
