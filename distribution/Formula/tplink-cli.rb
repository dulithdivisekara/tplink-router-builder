class TplinkCli < Formula
  desc "Universal TP-Link Router Suite CLI & Network Optimization"
  homepage "https://github.com/dulithdivisekara/tplink-router-suite"
  url "https://github.com/dulithdivisekara/tplink-router-suite/archive/refs/tags/v1.1.0.tar.gz"
  license "MIT"
  head "https://github.com/dulithdivisekara/tplink-router-suite.git", branch: "main"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/tplink-cli", "profile", "check", "--force"
  end
end
