package com.twitter.mesos.scheduler.storage;

import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import com.google.common.testing.TearDown;
import com.google.common.testing.junit4.TearDownTestCase;
import com.google.common.util.concurrent.ThreadFactoryBuilder;

import org.junit.Before;
import org.junit.Test;

import com.twitter.common.quantity.Amount;
import com.twitter.common.quantity.Time;
import com.twitter.common.util.concurrent.ExecutorServiceShutdown;

import static org.junit.Assert.assertEquals;

public class LockManagerTest extends TearDownTestCase {

  private LockManager lockManager;
  private ExecutorService executor;

  @Before
  public void setUp() {
    lockManager = new LockManager();
    executor = Executors.newCachedThreadPool(
        new ThreadFactoryBuilder().setNameFormat("LockManagerTest-%d").setDaemon(true).build());
    addTearDown(new TearDown() {
      @Override
      public void tearDown() {
        new ExecutorServiceShutdown(executor, Amount.of(1L, Time.SECONDS)).execute();
      }
    });
  }

  @Test
  public void testModeDowngrade() {
    lockManager.writeLock();
    lockManager.readLock();
  }

  @Test(expected = IllegalStateException.class)
  public void testModeUpgrade() {
    lockManager.readLock();
    lockManager.writeLock();
  }

  @Test
  public void testSimultaneousReads() throws Exception {
    final CountDownLatch slowReadStarted = new CountDownLatch(1);
    final CountDownLatch fastReadFinished = new CountDownLatch(1);

    Future<String> slowReadResult = executor.submit(new Callable<String>() {
      @Override public String call() throws Exception {
        lockManager.readLock();
        slowReadStarted.countDown();
        fastReadFinished.await();
        lockManager.readUnlock();
        return "slow";
      }
    });

    slowReadStarted.await();
    lockManager.readLock();
    lockManager.readUnlock();
    fastReadFinished.countDown();
    assertEquals("slow", slowReadResult.get());
  }
}
