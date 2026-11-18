import 'package:flet/flet.dart';

import 'flet_health_steps.dart';

class Extension extends FletExtension {
  @override
  FletService? createService(Control control) {
    switch (control.type) {
      case "FletHealthSteps":
        return FletHealthStepsService(control: control);
      default:
        return null;
    }
  }
}
