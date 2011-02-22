package com.twitter.mesos;

import com.google.inject.Binder;

import com.twitter.common.process.GuicedProcess;

/**
 * Utility class to register HTTP resources for mesos dashboards.
 *
 * @author wfarner
 */
public class HttpAssets {

  public static void register(Binder binder) {
    GuicedProcess.registerHttpAsset(binder, "/js/mootools-core.js", HttpAssets.class,
        "js/mootools-core.js", "application/javascript", true);
    GuicedProcess.registerHttpAsset(binder, "/js/mootools-more.js", HttpAssets.class,
        "js/mootools-more.js", "application/javascript", true);
    GuicedProcess.registerHttpAsset(binder, "/js/tit.js", HttpAssets.class,
        "js/tit.js", "application/javascript", true);
    GuicedProcess.registerHttpAsset(binder, "/css/global.css", HttpAssets.class,
        "css/global.css", "text/css", true);
  }

  private HttpAssets() {
    // Utility.
  }
}