import Foundation
import Cocoa
import Vision

struct OCRItem: Codable {
    let text: String
    let x0: Double
    let y0: Double
    let x1: Double
    let y1: Double
    let confidence: Double
}

func runOCR(imagePath: String) {
    guard let nsImage = NSImage(contentsOfFile: imagePath),
          let cgImage = nsImage.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        fputs("Error: Could not load image at \(imagePath)\n", stderr)
        print("[]")
        return
    }

    let imgWidth = Double(cgImage.width)
    let imgHeight = Double(cgImage.height)

    var results: [OCRItem] = []

    let request = VNRecognizeTextRequest { request, error in
        guard let observations = request.results as? [VNRecognizedTextObservation] else { return }
        for obs in observations {
            guard let candidate = obs.topCandidates(1).first else { continue }
            let text = candidate.string.trimmingCharacters(in: .whitespacesAndNewlines)
            if text.isEmpty { continue }

            // Vision uses bottom-left origin normalized coordinates (0..1)
            let box = obs.boundingBox
            let x0 = box.origin.x * imgWidth
            let x1 = (box.origin.x + box.size.width) * imgWidth
            // Convert to top-left origin
            let y0 = (1.0 - box.origin.y - box.size.height) * imgHeight
            let y1 = (1.0 - box.origin.y) * imgHeight

            results.append(OCRItem(
                text: text,
                x0: Double(round(x0 * 10) / 10),
                y0: Double(round(y0 * 10) / 10),
                x1: Double(round(x1 * 10) / 10),
                y1: Double(round(y1 * 10) / 10),
                confidence: Double(round(candidate.confidence * 100) / 100)
            ))
        }
    }

    request.recognitionLanguages = ["pt-BR", "pt-PT", "en-US", "es-ES", "it-IT", "fr-FR"]
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
        let encoder = JSONEncoder()
        let data = try encoder.encode(results)
        if let jsonStr = String(data: data, encoding: .utf8) {
            print(jsonStr)
        }
    } catch {
        print("[]")
    }
}

let args = CommandLine.arguments
if args.count > 1 {
    runOCR(imagePath: args[1])
} else {
    print("[]")
}
