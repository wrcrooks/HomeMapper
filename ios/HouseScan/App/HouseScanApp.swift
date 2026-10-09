import SwiftUI
import RoomPlan

@main
struct HouseScanApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

/// Phase 0 placeholder: proves the build → sideload pipeline and reports RoomPlan support.
struct ContentView: View {
    private let roomPlanSupported = RoomCaptureSession.isSupported

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "house.lodge")
                .font(.system(size: 64))
            Text("HouseScan")
                .font(.largeTitle.bold())
            Label(
                roomPlanSupported ? "RoomPlan supported" : "RoomPlan NOT supported on this device",
                systemImage: roomPlanSupported ? "checkmark.circle.fill" : "xmark.octagon.fill"
            )
            .foregroundStyle(roomPlanSupported ? .green : .red)
            Text(versionString)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding()
    }

    private var versionString: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "?"
        let build = info?["CFBundleVersion"] as? String ?? "?"
        return "v\(version) (\(build))"
    }
}
