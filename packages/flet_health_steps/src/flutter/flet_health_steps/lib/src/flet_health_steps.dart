import 'dart:async';

import 'package:flet/flet.dart';
import 'package:flutter/foundation.dart';
import 'package:health/health.dart';
import 'package:pedometer/pedometer.dart';
import 'package:permission_handler/permission_handler.dart';

class FletHealthStepsService extends FletService {
  final Health _health = Health();
  bool _healthConfigured = false;
  StreamSubscription<StepCount>? _stepSub;
  StreamSubscription<PedestrianStatus>? _statusSub;
  int? _latestRawSteps;
  String _pedestrianStatus = "unknown";

  static final List<HealthDataType> _stepTypes = [HealthDataType.STEPS];
  static final List<HealthDataAccess> _readPermissions = [
    HealthDataAccess.READ,
  ];

  FletHealthStepsService({required super.control});

  bool get _isMobile => !kIsWeb && (Platform.isAndroid || Platform.isIOS);

  @override
  void init() {
    super.init();
    debugPrint("FletHealthStepsService(${control.id}).init");
    control.addInvokeMethodListener(_invokeMethod);
  }

  Future<void> _ensureConfigured() async {
    if (!_healthConfigured) {
      await _health.configure();
      _healthConfigured = true;
    }
  }

  Future<bool> _isHealthConnectAvailable() async {
    if (!Platform.isAndroid) {
      return Platform.isIOS;
    }
    await _ensureConfigured();
    final status = await _health.getHealthConnectSdkStatus();
    return status == HealthConnectSdkStatus.sdkAvailable;
  }

  Future<Map<String, dynamic>> _startPedometer({bool requestPerm = true}) async {
    if (!_isMobile) {
      return {"active": false, "reason": "unsupported_platform"};
    }
    if (Platform.isAndroid && requestPerm) {
      final perm = await Permission.activityRecognition.request();
      if (!perm.isGranted) {
        return {"active": false, "reason": "permission_denied"};
      }
    }
    try {
      await _stepSub?.cancel();
      _stepSub = Pedometer.stepCountStream.listen(
        (StepCount event) {
          _latestRawSteps = event.steps;
          control.triggerEvent("sensor_step", {
            "raw_steps": event.steps,
            "timestamp": event.timeStamp.toIso8601String(),
          });
        },
        onError: (Object error) {
          debugPrint("FletHealthStepsService step stream error: $error");
          control.triggerEvent("sensor_error", {"message": error.toString()});
        },
      );

      await _statusSub?.cancel();
      _statusSub = Pedometer.pedestrianStatusStream.listen(
        (PedestrianStatus event) {
          _pedestrianStatus = event.status;
          control.triggerEvent("pedestrian_status", {
            "status": event.status,
            "timestamp": event.timeStamp.toIso8601String(),
          });
        },
        onError: (Object error) {
          debugPrint("FletHealthStepsService pedestrian status error: $error");
        },
      );

      return {"active": true, "raw_steps": _latestRawSteps};
    } catch (e) {
      return {"active": false, "reason": e.toString()};
    }
  }

  Future<dynamic> _invokeMethod(String name, dynamic args) async {
    final argMap = args is Map ? Map<String, dynamic>.from(args) : <String, dynamic>{};

    switch (name) {
      case "is_supported":
        return {
          "supported": _isMobile,
          "platform": kIsWeb ? "web" : Platform.operatingSystem,
        };

      case "check_health_connect_status":
        if (!_isMobile) {
          return {"available": false, "status": "unsupported_platform"};
        }
        if (!Platform.isAndroid) {
          return {"available": Platform.isIOS, "status": "healthkit"};
        }
        try {
          await _ensureConfigured();
          final sdkStatus = await _health.getHealthConnectSdkStatus();
          return {
            "available": sdkStatus == HealthConnectSdkStatus.sdkAvailable,
            "status": sdkStatus?.name ?? "unknown",
          };
        } catch (e) {
          return {"available": false, "status": "error", "error": e.toString()};
        }

      case "install_health_connect":
        if (!kIsWeb && Platform.isAndroid) {
          await _ensureConfigured();
          await _health.installHealthConnect();
          return true;
        }
        return false;

      case "request_permissions":
        if (!_isMobile) {
          return {
            "activity_recognition": false,
            "health_connect": false,
            "pedometer_active": false,
          };
        }

        bool activityGranted = true;
        if (Platform.isAndroid) {
          final status = await Permission.activityRecognition.request();
          activityGranted = status.isGranted;
        }

        bool hcGranted = false;
        String? hcError;
        try {
          if (await _isHealthConnectAvailable()) {
            bool? hasPerm = await _health.hasPermissions(
              _stepTypes,
              permissions: _readPermissions,
            );
            if (hasPerm != true) {
              hasPerm = await _health.requestAuthorization(
                _stepTypes,
                permissions: _readPermissions,
              );
            }
            hcGranted = hasPerm == true;
          }
        } catch (e) {
          hcError = e.toString();
          debugPrint("Health Connect auth error: $e");
        }

        final pedRes = await _startPedometer(requestPerm: false);
        return {
          "activity_recognition": activityGranted,
          "health_connect": hcGranted,
          "pedometer_active": pedRes["active"] == true,
          "error": hcError,
        };

      case "get_steps_range":
        if (!_isMobile) {
          return {"ok": false, "steps": <String, int>{}, "error": "unsupported_platform"};
        }
        try {
          if (!await _isHealthConnectAvailable()) {
            return {"ok": false, "steps": <String, int>{}, "error": "health_connect_unavailable"};
          }
          final hasPerm = await _health.hasPermissions(
            _stepTypes,
            permissions: _readPermissions,
          );
          if (hasPerm != true) {
            return {"ok": false, "steps": <String, int>{}, "error": "permission_not_granted"};
          }

          final rawDates = (argMap["dates"] as List?) ?? <dynamic>[];
          final now = DateTime.now();
          final todayKey =
              "${now.year.toString().padLeft(4, '0')}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}";
          final result = <String, int>{};

          for (final item in rawDates) {
            final dateStr = item.toString();
            final parts = dateStr.split("-");
            if (parts.length != 3) continue;
            final y = int.tryParse(parts[0]);
            final m = int.tryParse(parts[1]);
            final d = int.tryParse(parts[2]);
            if (y == null || m == null || d == null) continue;

            final start = DateTime(y, m, d, 0, 0, 0);
            DateTime end = (dateStr == todayKey)
                ? now
                : DateTime(y, m, d, 23, 59, 59, 999);
            if (!end.isAfter(start)) {
              end = start.add(const Duration(seconds: 1));
            }
            final steps = await _health.getTotalStepsInInterval(start, end);
            result[dateStr] = steps ?? 0;
          }
          return {"ok": true, "steps": result, "error": null};
        } catch (e) {
          return {"ok": false, "steps": <String, int>{}, "error": e.toString()};
        }

      case "start_pedometer":
        return await _startPedometer(requestPerm: true);

      case "stop_pedometer":
        await _stepSub?.cancel();
        _stepSub = null;
        await _statusSub?.cancel();
        _statusSub = null;
        return true;

      case "get_latest_raw_steps":
        return {
          "raw_steps": _latestRawSteps,
          "pedestrian_status": _pedestrianStatus,
          "active": _stepSub != null,
        };

      default:
        throw Exception("Unknown FletHealthSteps method: $name");
    }
  }

  @override
  void dispose() {
    debugPrint("FletHealthStepsService(${control.id}).dispose()");
    control.removeInvokeMethodListener(_invokeMethod);
    _stepSub?.cancel();
    _stepSub = null;
    _statusSub?.cancel();
    _statusSub = null;
    super.dispose();
  }
}
