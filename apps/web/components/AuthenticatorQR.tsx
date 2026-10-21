"use client";
import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { securityCopy as copy } from "@/lib/strings/security";
export default function AuthenticatorQR({ uri }: { uri: string }) {
  const [image, setImage] = useState(""),
    [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    setImage("");
    setFailed(false);
    QRCode.toDataURL(uri, {
      width: 256,
      margin: 4,
      errorCorrectionLevel: "M",
      color: { dark: "#171717", light: "#ffffff" },
    })
      .then((value) => {
        if (live) setImage(value);
      })
      .catch(() => {
        if (live) setFailed(true);
      });
    return () => {
      live = false;
    };
  }, [uri]);
  return image ? (
    <img
      className="authenticatorQR"
      src={image}
      width={256}
      height={256}
      alt={copy.qr}
    />
  ) : (
    <p role="status">{failed ? copy.qrError : copy.loading}</p>
  );
}
