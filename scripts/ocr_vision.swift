// ocr_vision.swift — 基于 Apple Vision 框架的中英文 OCR 助手
// 用法: ocr_vision <image_path> [--sort]
// 输出: 每行 "x y w h<TAB>文本"（Vision 归一化坐标，原点在左下）
import Foundation
import Vision
import AppKit

let args = CommandLine.arguments
guard args.count >= 2 else {
    print("ERR: usage: ocr_vision <image_path> [--sort]")
    exit(1)
}
let path = args[1]
let doSort = args.contains("--sort")

guard let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("ERR: cannot load image: \(path)")
    exit(1)
}

let request = VNRecognizeTextRequest { req, _ in
    guard let obs = req.results as? [VNRecognizedTextObservation] else { return }
    var lines: [(Double, Double, Double, Double, String)] = []
    for o in obs {
        if let t = o.topCandidates(1).first {
            let b = o.boundingBox
            lines.append((b.origin.x, b.origin.y, b.size.width, b.size.height, t.string))
        }
    }
    if doSort {
        // 按行（y 从高到低）→ 列（x 从左到右）排序，模拟阅读顺序
        lines.sort {
            let y0 = Int($0.1 / 0.03), y1 = Int($1.1 / 0.03)
            if y0 != y1 { return y0 > y1 }
            return $0.0 < $1.0
        }
    }
    for (x, y, w, h, s) in lines {
        print(String(format: "%.3f %.3f %.3f %.3f\t%@", x, y, w, h, s))
    }
}
request.recognitionLevel = .accurate
request.recognitionLanguages = ["zh-Hans", "en-US"]
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cg, options: [:])
do {
    try handler.perform([request])
} catch {
    print("ERR: \(error)")
    exit(1)
}
