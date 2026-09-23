const stringToColor = (str) => {
  if (str === undefined) {
    return "#cccccc";
  }

  let hash = 0;
  let color = "#";

  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }

  for (let i = 0; i < 3; i++) {
    let value = (hash >> (i * 8)) & 0xff;
    color += ("00" + value.toString(16)).substr(-2);
  }

  return color;
};

export const colorForOoi = (ooiType) => {
  const colors = {
    dnsNameServer: "#FFDFD3",
    dnsRecord: "#98E2F7",
    dnsSoa: "#F7C5DD",
    dnsZone: "#FFBD33",
    ipAddress: "#D0B1FC",
  };

  if (Object.keys(colors).includes(ooiType)) {
    return colors[ooiType];
  }

  return stringToColor(ooiType);
};

export const truncateText = (text, length, truncateCenter = true) => {
  if (!text) {
    return "";
  }

  if (text.length <= length) {
    return text;
  }

  if (!truncateCenter) {
    return text.substring(0, length - 3) + "…";
  }

  const startLength = 8;
  const endLength = length - startLength - 3;

  return text.substring(0, startLength) + "…" + text.slice(-endLength);
};
